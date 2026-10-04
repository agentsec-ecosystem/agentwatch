"""``agentwatch at`` — the cross-session time window (M17 S24, PRD 33).

No incident arrives as a session id; it arrives as "prod broke around 2pm". This
returns every record in a window, across every session and project, time-ordered,
with a header naming the active sessions and stating whether recording had a gap
in the window. Time is echoed as the resolved UTC range so timezone confusion is
visible, never silent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo

from agentwatch.recorder_state import MARKER_TOOLS, CoverageWindow, coverage_windows
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

DEFAULT_WINDOW = "30m"

_RELATIVE = re.compile(r"^(\d+)([smhd])$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# Records that are recorder bookkeeping, not agent activity.
_NON_ACTIVITY = frozenset(
    {
        "store-access",
        "harness-drift",
        "archive-anchor",
        "archive-restored",
        *MARKER_TOOLS,
    }
)


def _local_tz() -> tzinfo:
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_duration(text: str) -> timedelta:
    """Parse ``30m``/``12h``/``2d``/``45s`` into a duration."""
    match = _RELATIVE.match(text.strip())
    if match is None:
        raise ValueError(f"invalid duration {text!r}; expected e.g. 30m, 12h, 2d")
    return timedelta(seconds=int(match.group(1)) * _UNIT[match.group(2)])


def parse_moment(text: str, *, local_tz: tzinfo | None = None) -> datetime:
    """Parse a moment: explicit offset/``Z`` as given, else interpreted as local."""
    normalized = text.strip().replace(" ", "T", 1)
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz or _local_tz())
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class WindowRecord:
    """One record in the window, flattened for rendering."""

    at: datetime
    session_id: str
    project: str | None
    agent: str
    tool: str
    outcome: str
    approval: str | None


@dataclass(frozen=True)
class WindowReport:
    """Every record in a cross-session window."""

    requested: str
    window: str
    start_utc: datetime
    end_utc: datetime
    records: tuple[WindowRecord, ...] = ()
    gap: bool | None = None
    gap_reason: str | None = None
    note: str | None = None

    @property
    def sessions(self) -> tuple[str, ...]:
        order: list[str] = []
        for record in self.records:
            if record.session_id not in order:
                order.append(record.session_id)
        return tuple(order)

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "window": self.window,
            "start_utc": self.start_utc.isoformat(),
            "end_utc": self.end_utc.isoformat(),
            "sessions": list(self.sessions),
            "gap": self.gap,
            "gap_reason": self.gap_reason,
            "note": self.note,
            "records": [
                {
                    "at": record.at.isoformat(),
                    "session_id": record.session_id,
                    "project": record.project,
                    "agent": record.agent,
                    "tool": record.tool,
                    "outcome": record.outcome,
                    "approval": record.approval,
                }
                for record in self.records
            ],
        }


def build_window(
    store: RecordStore,
    moment: str,
    *,
    window: str = DEFAULT_WINDOW,
    local_tz: tzinfo | None = None,
) -> WindowReport:
    """Collect every record in ``[moment, moment+window)`` across all sessions."""
    start = parse_moment(moment, local_tz=local_tz)
    end = start + parse_duration(window)

    records: list[AgentRecord] = [
        record
        for record in store.records()
        if record.tool.name not in _NON_ACTIVITY and start <= record.started_at < end
    ]
    records.sort(key=lambda record: record.started_at)

    gap_records = [
        record
        for record in store.records()
        if record.tool.name == "recording-gap" and start <= record.started_at < end
    ]
    windows = coverage_windows(store)
    gap, gap_reason = _gap_state(windows, start, end, bool(gap_records))
    note = _note(records, windows, gap)
    return WindowReport(
        requested=moment,
        window=window,
        start_utc=start,
        end_utc=end,
        records=tuple(_flat(record) for record in records),
        gap=gap,
        gap_reason=gap_reason,
        note=note,
    )


def _gap_state(
    windows: list[CoverageWindow], start: datetime, end: datetime, has_gap_record: bool
) -> tuple[bool | None, str | None]:
    if has_gap_record:
        return True, "recording-gap record in window"
    if not windows:
        return None, None
    covered = False
    for window in windows:
        if window.opened_at <= start and (window.closed_at is None or window.closed_at >= end):
            covered = True
            break
    if covered:
        return False, None
    return True, "window not covered by a coverage record"


def _note(
    records: list[AgentRecord], windows: list[CoverageWindow], gap: bool | None
) -> str | None:
    if records:
        return None
    if gap:
        return "nothing was watched (recording gap in this window)"
    if not windows:
        return "nothing recorded and no coverage data for this window"
    return "nothing happened (recording was active)"


def _flat(record: AgentRecord) -> WindowRecord:
    approval = None
    if record.tool.arguments is not None:
        value = record.tool.arguments.get("approval")
        if isinstance(value, str):
            approval = value
    return WindowRecord(
        at=record.started_at,
        session_id=record.session_id,
        project=record.project,
        agent=record.agent.identity or record.agent.name or "unknown",
        tool=record.tool.name,
        outcome=record.outcome.value,
        approval=approval,
    )


def render_window(report: WindowReport) -> str:
    """Render the window header + time-ordered records."""
    lines = [
        f"agentwatch at {report.requested} (window {report.window})",
        f"  resolved UTC range: {report.start_utc.isoformat()} .. {report.end_utc.isoformat()}",
        f"  sessions: {', '.join(report.sessions) if report.sessions else 'none'}",
    ]
    if report.gap is True:
        lines.append(f"  gap: yes ({report.gap_reason})")
    elif report.gap is False:
        lines.append("  gap: no")
    else:
        lines.append("  gap: unknown (no coverage data)")
    if report.note:
        lines.append(f"  {report.note}")
    for record in report.records:
        approval = f" approval={record.approval}" if record.approval else ""
        lines.append(
            f"  {record.at.isoformat()} {record.session_id} {record.project or '-'} "
            f"{record.agent} {record.tool} {record.outcome}{approval}"
        )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_WINDOW",
    "WindowRecord",
    "WindowReport",
    "build_window",
    "parse_duration",
    "parse_moment",
    "render_window",
]
