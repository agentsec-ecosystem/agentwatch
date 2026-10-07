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

from agentwatch.cost import build_cost
from agentwatch.denials import DenialSequence, denial_sequences
from agentwatch.inventory import build_inventory
from agentwatch.oversight import build_oversight
from agentwatch.query import since_cutoff
from agentwatch.recorder_state import coverage_windows
from agentwatch.store import RecordStore

DEFAULT_DIGEST_WINDOW = "7d"
TOP_TOOLS = 10


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
    "DigestReport",
    "build_digest",
    "render_digest",
]
