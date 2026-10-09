"""Denied-then-retried sequences (M17 S25, PRD 33).

A denial recorded in isolation hides the pattern that matters: a call is refused,
then the agent tries the same end by another route. For each ``denied`` record,
this surfaces the **next N calls in the session** as its follow-up window, with
neutral naming ("followed within N calls by …") and **no severity or verdict** —
it is a detector input, not a detector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agentwatch.records import AgentRecord

# D-32.5: the follow-up window size.
FOLLOW_UP_N = 3

_INTERNAL_TOOLS = frozenset(
    {
        "session-usage",
        "recording-gap",
        "hook-error",
        "operator-note",
        "store-access",
        "key-rotation",
        "harness-drift",
        "external-event",
        "archive-anchor",
        "archive-restored",
        "recorder-installed",
        "recorder-uninstalled",
        "config-changed",
        "privacy-mode-changed",
        "retention-changed",
        "export-configured",
        "coverage-window-open",
        "coverage-window-close",
    }
)
ACTIVITY = "activity"


@dataclass(frozen=True)
class FollowUp:
    """One call in a denial's follow-up window."""

    tool: str
    outcome: str
    at: datetime
    category: str | None = None


@dataclass(frozen=True)
class DenialSequence:
    """A denial and the calls that followed it within N."""

    session_id: str
    denied_tool: str
    denied_at: datetime
    reason: str | None
    follow_ups: tuple[FollowUp, ...] = ()

    @property
    def empty(self) -> bool:
        """Whether the session ended (or no calls followed) after the denial."""
        return not self.follow_ups

    def render(self) -> str:
        """A neutral one-line description (no severity)."""
        head = f"{self.denied_at.isoformat()} denied {self.denied_tool}"
        if self.reason:
            head += f" ({self.reason})"
        if not self.follow_ups:
            return f"{head} → no follow-up calls (session ended)"
        followed = ", ".join(f"{f.tool}({f.outcome})" for f in self.follow_ups)
        return f"{head} → followed within {FOLLOW_UP_N} calls by: {followed}"


def _reason(record: AgentRecord) -> str | None:
    if record.security_event is not None and record.security_event.reason:
        return record.security_event.reason
    arguments = record.tool.arguments
    if arguments is not None:
        value = arguments.get("reason")
        if isinstance(value, str):
            return value
    return None


def denial_sequences(records: list[AgentRecord]) -> tuple[DenialSequence, ...]:
    """Every denial with its follow-up window, in session order."""
    ordered = [record for record in records if record.tool.name not in _INTERNAL_TOOLS]
    sequences: list[DenialSequence] = []
    for index, record in enumerate(ordered):
        if record.outcome.value != "denied":
            continue
        follow_ups = tuple(
            FollowUp(
                tool=later.tool.name,
                outcome=later.outcome.value,
                at=later.started_at,
                category=ACTIVITY,
            )
            for later in ordered[index + 1 : index + 1 + FOLLOW_UP_N]
        )
        sequences.append(
            DenialSequence(
                session_id=record.session_id,
                denied_tool=record.tool.name,
                denied_at=record.started_at,
                reason=_reason(record),
                follow_ups=follow_ups,
            )
        )
    return tuple(sequences)


def render_sequences(sequences: tuple[DenialSequence, ...]) -> str:
    """Render a neutral ``denied → followed by`` block, or "" when none."""
    if not sequences:
        return ""
    lines = ["denied → followed by (observation only; no severity):"]
    lines.extend(f"  {sequence.render()}" for sequence in sequences)
    return "\n".join(lines)


__all__ = [
    "FOLLOW_UP_N",
    "DenialSequence",
    "FollowUp",
    "denial_sequences",
    "render_sequences",
]
