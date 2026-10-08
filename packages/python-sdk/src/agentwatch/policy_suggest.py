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

from dataclasses import dataclass, field
from datetime import datetime
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


__all__ = [
    "FORMAT_VERSION",
    "INTERPRETER_TOOLS",
    "NEVER_ALLOW",
    "TARGETS",
    "Evidence",
    "LintFinding",
    "PolicySuggestion",
    "Rule",
    "lint_rules",
    "render_policy_suggestion",
    "suggest_policy",
    "suggestion_to_dict",
]
