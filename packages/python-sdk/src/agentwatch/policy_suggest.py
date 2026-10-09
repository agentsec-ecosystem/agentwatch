"""``suggest-policy`` + dangerous-broad lint (M30 POL-1, #469).

Users approve the overwhelming majority of prompts, and broad allow-rules grant
arbitrary execution; a tamper-evident history is the only defensible source for a
*tighter* policy. But agentwatch is **monitor-only**: this module emits an inert
suggestion (a file or diff) from observed calls and cls1 classes, with a lint of
dangerous-broad rules. It never applies a policy, never edits harness settings,
and names agentpolicy as the consumer (ADR-0038).

Rules carry evidence (calls, sessions, approvals, last-seen). Classes
``command:destructive``, ``network:destination`` and ``credential:adjacent`` are
**never** suggested as ``allow`` by default; an explicit ``include`` promotes
them, and they stay annotated. Output is deterministic and states the window,
record count and coverage gaps.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentwatch.classify import (
    CLASSIFIER_VERSION,
    CMD_DESTRUCTIVE,
    CREDENTIAL,
    NETWORK,
    UNCLASSIFIED,
    classify_record,
)
from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord, effective_authorization
from agentwatch.store import RecordStore
from agentwatch.store_access import STORE_ACCESS_TOOL

#: Published format version stamped into every suggestion.
FORMAT_VERSION = "policy-suggest-v1"

#: Format of a policy file consumed by ``what-if`` (hand-written or a suggestion).
POLICY_FORMAT_VERSION = "agentwatch-policy/1"

#: Format of the ``what-if`` simulation report.
WHATIF_FORMAT_VERSION = "policy-whatif-v1"

#: The output targets a consumer (agentpolicy) understands.
TARGETS: tuple[str, ...] = ("claude-settings", "mcp-allowlist", "acs")

#: Classes that are never suggested as ``allow`` without an explicit opt-in.
NEVER_ALLOW: tuple[str, ...] = (CMD_DESTRUCTIVE, NETWORK, CREDENTIAL)

#: Tools that run arbitrary programs; a bare/wildcard rule is broad by nature.
INTERPRETER_TOOLS: frozenset[str] = frozenset(
    {"bash", "shell", "sh", "exec", "python", "python3", "node"}
)

#: Argument keys that carry a shell command.
_COMMAND_KEYS = ("command", "cmd", "script", "input")

_ADVISORY_NOTE = (
    "Advisory only — agentwatch generates and simulates; it never enforces. "
    "Apply via agentpolicy; nothing here edits harness settings."
)


@dataclass(frozen=True)
class Evidence:
    """Why a rule exists: the observed calls behind it."""

    calls: int
    sessions: tuple[str, ...] = ()
    approvals: tuple[str, ...] = ()
    last_seen: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "sessions": list(self.sessions),
            "approvals": list(self.approvals),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


@dataclass(frozen=True)
class Rule:
    """One advisory allow/ask/deny candidate."""

    id: str
    effect: str
    tool: str
    matcher: str
    categories: tuple[str, ...]
    rationale: str
    evidence: Evidence = field(default_factory=lambda: Evidence(calls=0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "effect": self.effect,
            "tool": self.tool,
            "matcher": self.matcher,
            "categories": list(self.categories),
            "rationale": self.rationale,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class LintFinding:
    """A dangerous-broad warning about a candidate rule."""

    rule_id: str
    kind: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "kind": self.kind, "message": self.message}


@dataclass(frozen=True)
class PolicySuggestion:
    """The whole advisory artifact (never applied)."""

    format_version: str
    target: str
    window: str
    records: int
    taxonomy_version: str
    coverage_gaps: tuple[str, ...]
    rules: tuple[Rule, ...]
    lint: tuple[LintFinding, ...]
    notes: tuple[str, ...]
    document: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "target": self.target,
            "window": self.window,
            "records": self.records,
            "taxonomy_version": self.taxonomy_version,
            "coverage_gaps": list(self.coverage_gaps),
            "rules": [rule.to_dict() for rule in self.rules],
            "lint": [finding.to_dict() for finding in self.lint],
            "notes": list(self.notes),
            "document": self.document,
        }


def _program(record: AgentRecord) -> str | None:
    arguments = record.tool.arguments
    if not isinstance(arguments, dict):
        return None
    for key in _COMMAND_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().split()[0]
    return None


def _is_shell(tool: str) -> bool:
    return tool.lower() in INTERPRETER_TOOLS


def lint_rules(rules: list[Rule] | tuple[Rule, ...]) -> list[LintFinding]:
    """Flag dangerous-broad rules (wildcard interpreter/exec, wildcard network)."""
    findings: list[LintFinding] = []
    for rule in rules:
        if _is_shell(rule.tool) and ("(" not in rule.matcher or "(*)" in rule.matcher):
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    kind="interpreter/exec",
                    message=(
                        f"{rule.matcher!r} allows an interpreter with no program scope; "
                        "prefer command-scoped rules"
                    ),
                )
            )
        if NETWORK in rule.categories and (
            rule.effect == "allow" or "(*)" in rule.matcher
        ):
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    kind="network",
                    message=(
                        f"{rule.matcher!r} grants network access; prefer destination-scoped rules"
                    ),
                )
            )
    return findings


def _group(records: list[AgentRecord]) -> tuple[dict[str, list[AgentRecord]], list[str]]:
    groups: dict[str, list[AgentRecord]] = {}
    gaps: list[str] = []
    for record in records:
        if _is_shell(record.tool.name):
            program = _program(record)
            if program is None:
                groups.setdefault(record.tool.name, []).append(record)
                gaps.append(
                    f"session {record.session_id}: shell call with no captured program "
                    f"({record.tool.name}) — cannot be command-scoped"
                )
                continue
            key = f"{record.tool.name}({program}:*)"
        else:
            key = record.tool.name
        groups.setdefault(key, []).append(record)
    return groups, gaps


def _categories(records: list[AgentRecord]) -> tuple[str, ...]:
    found: set[str] = set()
    for record in records:
        for fact in classify_record(record):
            found.add(fact.category)
    if not found:
        found.add(UNCLASSIFIED)
    return tuple(sorted(found))


def _evidence(records: list[AgentRecord]) -> Evidence:
    sessions = tuple(sorted({record.session_id for record in records}))
    approvals = tuple(
        sorted({effective_authorization(record).source.value for record in records})
    )
    last_seen = max((record.started_at for record in records), default=None)
    return Evidence(calls=len(records), sessions=sessions, approvals=approvals, last_seen=last_seen)


def _effect(
    records: list[AgentRecord], categories: tuple[str, ...], *, include: bool
) -> str:
    denied = sum(1 for record in records if record.outcome.value == "denied")
    if denied and denied == len(records):
        return "deny"
    if not include and set(categories) & set(NEVER_ALLOW):
        return "ask"
    return "allow"


def _document(target: str, rules: tuple[Rule, ...]) -> dict[str, Any]:
    buckets: dict[str, list[str]] = {"allow": [], "ask": [], "deny": []}
    for rule in rules:
        buckets[rule.effect].append(rule.matcher)
    if target == "claude-settings":
        return {"permissions": {effect: sorted(items) for effect, items in buckets.items()}}
    if target == "mcp-allowlist":
        return {"tools": {effect: sorted(items) for effect, items in buckets.items()}}
    return {
        "acs": {
            "revision": "v0.1.0",
            **{effect: sorted(items) for effect, items in buckets.items()},
        }
    }


def suggest_policy(
    store: RecordStore,
    *,
    since: str | None = None,
    target: str = "claude-settings",
    project: str | None = None,
    include: bool = False,
    now: datetime | None = None,
) -> PolicySuggestion:
    """Derive an advisory least-privilege suggestion from observed history."""
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {', '.join(TARGETS)}")
    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record
        for record in store.records()
        if record.tool.name != STORE_ACCESS_TOOL
        and (cutoff is None or record.started_at >= cutoff)
        and (project is None or record.project == project)
    ]

    groups, gaps = _group(records)
    rules: list[Rule] = []
    for matcher in sorted(groups):
        members = groups[matcher]
        categories = _categories(members)
        effect = _effect(members, categories, include=include)
        tool = members[0].tool.name
        if effect == "deny":
            rationale = "every observed call was denied; a deny candidate"
        elif effect == "ask":
            flagged = sorted(set(categories) & set(NEVER_ALLOW))
            rationale = (
                f"observed but never recommend allowing by default ({', '.join(flagged)}); "
                "requires a prompt or explicit review"
            )
        else:
            rationale = "observed and allowed; a least-privilege allow candidate"
        rules.append(
            Rule(
                id=f"rule:{matcher}",
                effect=effect,
                tool=tool,
                matcher=matcher,
                categories=categories,
                rationale=rationale,
                evidence=_evidence(members),
            )
        )

    lint = lint_rules(rules)
    unique_gaps = tuple(sorted(set(gaps)))
    return PolicySuggestion(
        format_version=FORMAT_VERSION,
        target=target,
        window=since or "all",
        records=len(records),
        taxonomy_version=CLASSIFIER_VERSION,
        coverage_gaps=unique_gaps,
        rules=tuple(rules),
        lint=tuple(lint),
        notes=(_ADVISORY_NOTE,),
        document=_document(target, tuple(rules)),
    )


def suggestion_to_dict(suggestion: PolicySuggestion) -> dict[str, Any]:
    return suggestion.to_dict()


def render_policy_suggestion(suggestion: PolicySuggestion) -> str:
    """A human-readable advisory artifact (never applied)."""
    lines = [
        f"agentwatch suggest-policy — advisory only (format {suggestion.format_version})",
        f"target: {suggestion.target} · window: {suggestion.window} · "
        f"records: {suggestion.records} · taxonomy: {suggestion.taxonomy_version}",
    ]
    if suggestion.coverage_gaps:
        lines.append(f"coverage gaps: {len(suggestion.coverage_gaps)}")
        lines.extend(f"  - {gap}" for gap in suggestion.coverage_gaps)
    lines.append("")
    lines.append("rules (effect  matcher  calls/sessions):")
    for rule in suggestion.rules:
        lines.append(
            f"  {rule.effect:<5} {rule.matcher:<20} "
            f"{rule.evidence.calls} call(s) / {len(rule.evidence.sessions)} session(s)"
        )
    if suggestion.lint:
        lines.append("")
        lines.append("lint — dangerous-broad rules:")
        lines.extend(f"  [{finding.kind}] {finding.message}" for finding in suggestion.lint)
    lines.append("")
    lines.append(suggestion.notes[0])
    return "\n".join(lines)


# --- what-if: replay a candidate policy over history (M30 POL-2) ----------------

_MATCHER_RE = re.compile(r"^(?P<tool>[A-Za-z0-9_.-]+)(?:\((?P<program>[^()]+)\))?$")


class PolicyParseError(ValueError):
    """A policy file could not be parsed (an explicit, actionable error)."""


@dataclass(frozen=True)
class ParsedRule:
    """One policy rule in the supported matcher grammar."""

    matcher: str
    tool: str
    program: str | None
    effect: str


@dataclass(frozen=True)
class ParsedPolicy:
    """A parsed policy: supported rules plus any reported unsupported syntax."""

    format_version: str
    rules: tuple[ParsedRule, ...]
    unsupported: tuple[str, ...] = ()


def parse_policy(text: str) -> ParsedPolicy:
    """Parse a policy document; raise :class:`PolicyParseError` on bad structure.

    Matchers outside the grammar (``Tool`` or ``Tool(program:*)``) are reported in
    ``unsupported`` and ignored — never guessed.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PolicyParseError(f"invalid policy JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyParseError("policy must be a JSON object")
    format_version = data.get("format_version")
    if not isinstance(format_version, str) or not format_version:
        raise PolicyParseError("policy is missing format_version")
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise PolicyParseError("policy must have a non-empty rules list")

    rules: list[ParsedRule] = []
    unsupported: list[str] = []
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise PolicyParseError(f"rule {index}: must be an object")
        matcher = raw.get("matcher")
        effect = raw.get("effect")
        if not isinstance(matcher, str) or not matcher:
            raise PolicyParseError(f"rule {index}: missing matcher")
        if effect not in ("allow", "ask", "deny"):
            raise PolicyParseError(f"rule {index}: unsupported effect {effect!r}")
        match = _MATCHER_RE.match(matcher)
        if match is None:
            unsupported.append(f"rule {index}: unsupported matcher syntax {matcher!r}")
            continue
        program = match.group("program")
        if program is not None:
            if program.endswith(":*"):
                program = program[:-2]
            elif program != "*":
                unsupported.append(f"rule {index}: unsupported matcher syntax {matcher!r}")
                continue
        rules.append(
            ParsedRule(
                matcher=matcher,
                tool=match.group("tool"),
                program=program,
                effect=effect,
            )
        )
    return ParsedPolicy(
        format_version=format_version,
        rules=tuple(rules),
        unsupported=tuple(unsupported),
    )


def load_policy(path: Path | str) -> ParsedPolicy:
    """Read and parse a policy file; a missing file is an explicit error."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyParseError(f"cannot read policy file {path}: {exc}") from exc
    return parse_policy(text)


def _matches(rule: ParsedRule, record: AgentRecord) -> bool:
    if rule.tool != record.tool.name:
        return False
    if rule.program is None or rule.program == "*":
        return True
    return _program(record) == rule.program


def _policy_effect(policy: ParsedPolicy, record: AgentRecord) -> str:
    for rule in policy.rules:
        if _matches(rule, record):
            return rule.effect
    return "ask"  # unmatched calls are prompt candidates, never silently allowed


def _record_matcher(record: AgentRecord) -> str:
    if _is_shell(record.tool.name):
        program = _program(record)
        if program is not None:
            return f"{record.tool.name}({program}:*)"
    return record.tool.name


def _actual_behavior(record: AgentRecord) -> str:
    if record.outcome.value == "denied":
        return "denied"
    source = effective_authorization(record).source.value
    if source == "denied":
        return "denied"
    if source in ("human-once", "human-remembered", "classifier"):
        return "prompted"
    return "allowed"


_ACTUAL_TO_POLICY = {"denied": "deny", "prompted": "ask", "allowed": "allow"}


@dataclass(frozen=True)
class WhatIfReport:
    """A labeled simulation of one policy over history (never applied)."""

    format_version: str
    policy_format_version: str
    window: str
    records: int
    counts: dict[str, int]
    actual: dict[str, int]
    prompts_avoided: tuple[dict[str, Any], ...]
    would_be_denials: tuple[dict[str, Any], ...]
    authorization_differences: tuple[dict[str, Any], ...]
    unsupported: tuple[str, ...]
    simulation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "policy_format_version": self.policy_format_version,
            "window": self.window,
            "records": self.records,
            "simulation": self.simulation,
            "counts": dict(self.counts),
            "actual": dict(self.actual),
            "prompts_avoided": list(self.prompts_avoided),
            "would_be_denials": list(self.would_be_denials),
            "authorization_differences": list(self.authorization_differences),
            "unsupported": list(self.unsupported),
        }


def simulate_policy(
    store: RecordStore,
    policy: ParsedPolicy,
    *,
    since: str | None = None,
    project: str | None = None,
    now: datetime | None = None,
) -> WhatIfReport:
    """Replay ``policy`` over the window and report the delta vs actual behavior."""
    cutoff = since_cutoff(since, now=now) if since is not None else None
    records = [
        record
        for record in store.records()
        if record.tool.name != STORE_ACCESS_TOOL
        and (cutoff is None or record.started_at >= cutoff)
        and (project is None or record.project == project)
    ]

    counts = {"allow": 0, "ask": 0, "deny": 0}
    actual = {"allowed": 0, "prompted": 0, "denied": 0}
    prompts_avoided: list[dict[str, Any]] = []
    would_be_denials: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []

    for record in records:
        effect = _policy_effect(policy, record)
        behavior = _actual_behavior(record)
        counts[effect] += 1
        actual[behavior] += 1
        if effect == "allow" and behavior == "prompted":
            prompts_avoided.append(
                {
                    "session": record.session_id,
                    "tool": record.tool.name,
                    "matcher": _record_matcher(record),
                }
            )
        if effect == "deny":
            would_be_denials.append(
                {
                    "session": record.session_id,
                    "tool": record.tool.name,
                    "matcher": _record_matcher(record),
                    "actual": _ACTUAL_TO_POLICY[behavior],
                }
            )
        if effect != _ACTUAL_TO_POLICY[behavior]:
            differences.append(
                {
                    "session": record.session_id,
                    "tool": record.tool.name,
                    "matcher": _record_matcher(record),
                    "policy_effect": effect,
                    "actual": _ACTUAL_TO_POLICY[behavior],
                }
            )

    return WhatIfReport(
        format_version=WHATIF_FORMAT_VERSION,
        policy_format_version=policy.format_version,
        window=since or "all",
        records=len(records),
        counts=counts,
        actual=actual,
        prompts_avoided=tuple(prompts_avoided),
        would_be_denials=tuple(would_be_denials),
        authorization_differences=tuple(differences),
        unsupported=policy.unsupported,
    )


def whatif_to_dict(report: WhatIfReport) -> dict[str, Any]:
    return report.to_dict()


def render_whatif(report: WhatIfReport) -> str:
    """A human-readable simulation report (labeled, never applied)."""
    lines = [
        "agentwatch what-if — SIMULATION only; nothing is applied "
        f"(report {report.format_version}, policy {report.policy_format_version})",
        f"window: {report.window} · records: {report.records}",
        f"policy: allow={report.counts['allow']} ask={report.counts['ask']} "
        f"deny={report.counts['deny']}",
        f"actual: allowed={report.actual['allowed']} prompted={report.actual['prompted']} "
        f"denied={report.actual['denied']}",
        f"prompts avoided: {len(report.prompts_avoided)}",
    ]
    for entry in report.prompts_avoided:
        lines.append(f"  - {entry['session']} {entry['matcher']} (was a prompt)")
    lines.append(f"would-be denials: {len(report.would_be_denials)}")
    for entry in report.would_be_denials:
        lines.append(
            f"  - {entry['session']} {entry['matcher']} (actual: {entry['actual']})"
        )
    lines.append(f"authorization differences: {len(report.authorization_differences)}")
    for entry in report.authorization_differences:
        lines.append(
            f"  - {entry['session']} {entry['matcher']}: policy {entry['policy_effect']} "
            f"vs actual {entry['actual']}"
        )
    if report.unsupported:
        lines.append("unsupported syntax (ignored):")
        lines.extend(f"  - {item}" for item in report.unsupported)
    return "\n".join(lines)


__all__ = [
    "FORMAT_VERSION",
    "INTERPRETER_TOOLS",
    "NEVER_ALLOW",
    "POLICY_FORMAT_VERSION",
    "TARGETS",
    "WHATIF_FORMAT_VERSION",
    "Evidence",
    "LintFinding",
    "ParsedPolicy",
    "ParsedRule",
    "PolicyParseError",
    "PolicySuggestion",
    "Rule",
    "WhatIfReport",
    "lint_rules",
    "parse_policy",
    "render_policy_suggestion",
    "render_whatif",
    "simulate_policy",
    "suggest_policy",
    "suggestion_to_dict",
    "whatif_to_dict",
]
