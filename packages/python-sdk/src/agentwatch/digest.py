"""``agentwatch digest`` — the local weekly readout (M17 S37, PRD 33).

A recorder that is never read becomes one that gets uninstalled. This renders a
short markdown digest of the window — sessions, tool mix, cost, denials, security
events, gaps, notable sequences, and inventory — **locally**, on invocation only.
No scheduling, no notification, no egress.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from agentwatch.classify import WIDEST_ORDER, classify_record
from agentwatch.cost import build_cost
from agentwatch.denials import DenialSequence, denial_sequences
from agentwatch.fingerprint import action_tuple, session_behavior_digest
from agentwatch.inventory import build_inventory
from agentwatch.oversight import build_oversight
from agentwatch.query import since_cutoff
from agentwatch.recorder_state import coverage_windows
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

DEFAULT_DIGEST_WINDOW = "7d"
TOP_TOOLS = 10

# Recurring failure signatures (OUT-2). The grouping rules are versioned so a
# later tightening never silently redefines an old readout. Signature components:
# tool, error class, cls1 class, and the session behavior fingerprint (``bd1``).
SIGNATURES_VERSION = "sg1"
TOP_SIGNATURES = 5
SIGNATURE_COMPONENTS: tuple[str, ...] = ("tool", "error_class", "cls1_class", "fingerprint")

# Internal/marker tools are never agent behavior (mirrors ``bd1`` filtering).
_ANOMALY_EXCLUDED = frozenset({"agentwatch", "external"})


@dataclass(frozen=True)
class FailureSignature:
    """The versioned grouping key for one recurring failure pattern."""

    tool: str
    error_class: str
    cls1_class: str
    fingerprint: str

    def key(self) -> tuple[str, str, str, str]:
        return (self.tool, self.error_class, self.cls1_class, self.fingerprint)


@dataclass(frozen=True)
class FailurePattern:
    """One ranked, evidence-linked recurring failure signature."""

    signature: FailureSignature
    count: int
    previous_count: int
    first_seen: datetime
    last_seen: datetime
    sessions: tuple[str, ...] = ()

    @property
    def tool(self) -> str:
        return self.signature.tool

    @property
    def error_class(self) -> str:
        return self.signature.error_class

    @property
    def cls1_class(self) -> str:
        return self.signature.cls1_class

    @property
    def fingerprint(self) -> str:
        return self.signature.fingerprint

    @property
    def trend(self) -> str:
        if self.previous_count == 0:
            return "new"
        if self.count > self.previous_count:
            return "up"
        if self.count < self.previous_count:
            return "down"
        return "flat"

    def evidence(self) -> tuple[str, ...]:
        """Deterministic links to ``replay`` (per session) and ``diff`` (a pair)."""
        links = [f"replay {session}" for session in self.sessions]
        if len(self.sessions) >= 2:
            links.append(f"diff {self.sessions[0]} {self.sessions[1]}")
        return tuple(links)

    def render(self) -> str:
        return (
            f"{self.tool}/{self.error_class}/{self.cls1_class}"
            f" (trend {self.trend}; n={self.count}, prior={self.previous_count};"
            f" first {self.first_seen.isoformat()}; last {self.last_seen.isoformat()})"
        )


def signature_rules() -> tuple[str, ...]:
    """The published grouping-rule components, in signature order."""
    return SIGNATURE_COMPONENTS


def _normalize_error(raw: str) -> str:
    text = " ".join(raw.split()).lower()
    return text[:80] if text else "error"


def _error_class(record: AgentRecord) -> str:
    """The record's failure/anomaly class (a fact, never a verdict)."""
    if record.outcome.value == "denied":
        return "denied"
    response = record.tool.response or {}
    for field in ("error", "message"):
        value = response.get(field)
        if isinstance(value, str) and value.strip():
            return _normalize_error(value)
    if record.outcome.value == "error":
        return "error"
    if record.security_event is not None:
        return f"event:{record.security_event.type.value}"
    return "anomaly"


def _cls1_class(record: AgentRecord) -> str:
    """The record's most consequential ``cls1`` category (blast-radius order)."""
    facts = classify_record(record)
    if not facts:
        return "unclassified"
    return min(
        facts,
        key=lambda fact: WIDEST_ORDER.index(fact.category)
        if fact.category in WIDEST_ORDER
        else len(WIDEST_ORDER),
    ).category


def _is_failure(record: AgentRecord) -> bool:
    if action_tuple(record) is None:  # internal/marker tools are not behavior
        return False
    return record.outcome.value != "ok" or record.security_event is not None


def build_failure_patterns(
    store: RecordStore,
    *,
    cutoff: datetime,
    now: datetime,
    top: int = TOP_SIGNATURES,
) -> tuple[FailurePattern, ...]:
    """Group failed calls / anomalies by the versioned signature (deterministic)."""
    span = now - cutoff
    previous_cutoff = cutoff - span
    records = [
        record
        for record in store.records()
        if record.session_id not in _ANOMALY_EXCLUDED and _is_failure(record)
    ]
    fingerprints: dict[str, str] = {}

    def fingerprint_of(session: str) -> str:
        if session not in fingerprints:
            fingerprints[session] = session_behavior_digest(store, session)
        return fingerprints[session]

    current: dict[tuple[str, str, str, str], list[AgentRecord]] = {}
    previous: Counter[tuple[str, str, str, str]] = Counter()
    for record in records:
        signature = FailureSignature(
            tool=record.tool.name,
            error_class=_error_class(record),
            cls1_class=_cls1_class(record),
            fingerprint=fingerprint_of(record.session_id),
        ).key()
        if record.started_at >= cutoff:
            current.setdefault(signature, []).append(record)
        elif record.started_at >= previous_cutoff:
            previous[signature] += 1

    patterns: list[FailurePattern] = []
    for signature, group in current.items():
        ordered = sorted(group, key=lambda record: record.started_at)
        sessions: list[str] = []
        for record in ordered:
            if record.session_id not in sessions:
                sessions.append(record.session_id)
        patterns.append(
            FailurePattern(
                signature=FailureSignature(*signature),
                count=len(group),
                previous_count=previous[signature],
                first_seen=ordered[0].started_at,
                last_seen=ordered[-1].started_at,
                sessions=tuple(sessions),
            )
        )
    patterns.sort(key=lambda pattern: (-pattern.count, pattern.first_seen, pattern.signature.key()))
    return tuple(patterns[:top])


@dataclass(frozen=True)
class DigestReport:
    """The derived digest data (markdown rendered separately)."""

    since: str
    start_utc: datetime
    sessions: tuple[str, ...]
    records: int
    tool_mix: tuple[tuple[str, int], ...]
    total_tokens: int
    total_cost_usd: float | None
    pricing_version: str
    denials: int
    denial_sequences: tuple[DenialSequence, ...]
    security_events: dict[str, int]
    gaps: int
    coverage_active: bool | None
    agents_seen: tuple[str, ...]
    servers_seen: tuple[str, ...]
    oversight_calls: int = 0
    oversight_sources: tuple[tuple[str, int], ...] = ()
    oversight_human: tuple[int, int] = (0, 0)
    signatures: tuple[FailurePattern, ...] = ()
    signatures_version: str = SIGNATURES_VERSION

    @property
    def empty(self) -> bool:
        return self.records == 0


def build_digest(
    store: RecordStore,
    *,
    since: str = DEFAULT_DIGEST_WINDOW,
    now: datetime | None = None,
) -> DigestReport:
    """Derive the digest over the window (all local, nothing written)."""
    moment = now or datetime.now(timezone.utc)
    cutoff = since_cutoff(since, now=moment)
    records = [
        record
        for record in store.records()
        if record.started_at >= cutoff and record.session_id not in {"agentwatch", "external"}
    ]
    sessions: list[str] = []
    for record in records:
        if record.session_id not in sessions:
            sessions.append(record.session_id)

    tool_mix = Counter(
        record.tool.name for record in records if record.tool.name != "session-usage"
    )
    cost = build_cost(store, by="model", since=since, now=moment)
    security_events = Counter(
        record.security_event.type.value for record in records if record.security_event is not None
    )
    gaps = sum(1 for record in records if record.tool.name == "recording-gap")
    windows = coverage_windows(store)
    coverage_active: bool | None = windows[-1].active if windows else None

    inventory = build_inventory(store)
    agents_seen = tuple(
        sorted(agent.identity for agent in inventory.agents if agent.last_seen >= cutoff)
    )
    servers_seen = tuple(
        sorted(server.server for server in inventory.servers if server.last_seen >= cutoff)
    )
    oversight = build_oversight(store, since=since, now=moment)
    signatures = build_failure_patterns(store, cutoff=cutoff, now=moment)
    return DigestReport(
        since=since,
        start_utc=cutoff,
        sessions=tuple(sessions),
        records=len(records),
        tool_mix=tuple(tool_mix.most_common(TOP_TOOLS)),
        total_tokens=cost.total_tokens,
        total_cost_usd=cost.total_cost_usd,
        pricing_version=cost.pricing_version,
        denials=sum(1 for record in records if record.outcome.value == "denied"),
        denial_sequences=denial_sequences(records),
        security_events=dict(sorted(security_events.items())),
        gaps=gaps,
        coverage_active=coverage_active,
        agents_seen=agents_seen,
        servers_seen=servers_seen,
        oversight_calls=oversight.total_calls,
        oversight_sources=tuple(
            (row.source, row.calls) for row in oversight.sources
        ),
        oversight_human=(
            oversight.human.approved if oversight.human else 0,
            oversight.human.prompted if oversight.human else 0,
        ),
        signatures=signatures,
        signatures_version=SIGNATURES_VERSION,
    )


def render_digest(report: DigestReport) -> str:
    """Render the digest as short markdown (pasted by hand, never sent)."""
    if report.empty:
        return (
            f"# agentwatch digest — last {report.since}\n\n"
            "No agent activity recorded in this window.\n"
        )
    lines = [
        f"# agentwatch digest — last {report.since}",
        "",
        f"- window starts (UTC): {report.start_utc.isoformat()}",
        f"- sessions: {len(report.sessions)}",
        f"- records: {report.records}",
    ]
    cost = (
        "tokens only (price unknown)"
        if report.total_cost_usd is None
        else f"${report.total_cost_usd:.4f}"
    )
    lines.append(f"- cost: {cost} ({report.total_tokens} tokens, pricing {report.pricing_version})")
    if report.coverage_active is False:
        lines.append("- recording: **stopped** at the end of the window")
    elif report.coverage_active is True:
        lines.append("- recording: active")
    else:
        lines.append("- recording: no coverage data")
    if report.gaps:
        lines.append(f"- gaps: {report.gaps} recording-gap record(s)")
    lines.extend(["", "## Sessions", ""])
    lines.extend(f"- `{session}`" for session in report.sessions)
    lines.extend(["", "## Tool mix", ""])
    if report.tool_mix:
        lines.extend(f"- {tool}: {count}" for tool, count in report.tool_mix)
    else:
        lines.append("- none")
    if report.denials or report.denial_sequences:
        lines.extend(["", "## Denials", ""])
        lines.append(f"- denied calls: {report.denials}")
        for sequence in report.denial_sequences:
            lines.append(f"- {sequence.render()}")
    if report.security_events:
        lines.extend(["", "## Security events", ""])
        lines.extend(f"- {kind}: {count}" for kind, count in report.security_events.items())
    if report.signatures:
        lines.extend(
            ["", f"## Recurring failure signatures ({report.signatures_version})", ""]
        )
        for pattern in report.signatures:
            lines.append(f"- {pattern.render()}")
            links = "; ".join(f"`{link}`" for link in pattern.evidence())
            if links:
                lines.append(f"  - evidence: {links}")
    if report.agents_seen or report.servers_seen:
        lines.extend(["", "## Inventory seen this window", ""])
        lines.extend(f"- agent: `{agent}`" for agent in report.agents_seen)
        lines.extend(f"- MCP server: `{server}`" for server in report.servers_seen)
    lines.extend(["", "## Oversight", ""])
    lines.append(f"- calls with an authorization source: {report.oversight_calls}")
    if report.oversight_sources:
        mix = ", ".join(
            f"{source}={count}" for source, count in report.oversight_sources
        )
        lines.append(f"- authorization mix: {mix}")
    if report.oversight_human[1]:
        lines.append(
            f"- human-prompted approvals: {report.oversight_human[0]}/"
            f"{report.oversight_human[1]}"
        )
    lines.extend(
        [
            "",
            "_Generated locally by agentwatch; nothing was sent anywhere._",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEFAULT_DIGEST_WINDOW",
    "SIGNATURES_VERSION",
    "SIGNATURE_COMPONENTS",
    "TOP_SIGNATURES",
    "DigestReport",
    "FailurePattern",
    "FailureSignature",
    "build_digest",
    "build_failure_patterns",
    "render_digest",
    "signature_rules",
]
