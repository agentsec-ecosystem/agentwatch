"""``agentwatch diff``: behavioral diff of two sessions (M8 addition H2).

Answers "what changed between two sessions?" — tool mix added/removed, failed
counts, and record counts — over already-stored (redacted) records only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from agentwatch.env_fingerprint import (
    EnvironmentChange,
    EnvironmentFingerprint,
    environment_delta,
    environment_fingerprint,
    render_environment_delta,
)
from agentwatch.records import AgentRecord
from agentwatch.replay import replay_session
from agentwatch.session_state import session_state
from agentwatch.store import RecordStore


@dataclass(frozen=True)
class SessionDiff:
    """Structural differences between two sessions."""

    a: str
    b: str
    records_a: int
    records_b: int
    failed_a: int
    failed_b: int
    added_tools: tuple[str, ...]
    removed_tools: tuple[str, ...]
    state_a: str = "unknown"
    state_b: str = "unknown"
    environment_a: EnvironmentFingerprint = field(default_factory=EnvironmentFingerprint)
    environment_b: EnvironmentFingerprint = field(default_factory=EnvironmentFingerprint)
    environment_changes: tuple[EnvironmentChange, ...] = ()

    def render(self) -> str:
        lines = [
            f"diff {self.a} -> {self.b}",
            render_environment_delta(self.environment_changes),
            f"records: {self.records_a} -> {self.records_b}",
            f"failed: {self.failed_a} -> {self.failed_b}",
            f"state: {self.state_a} -> {self.state_b}",
        ]
        if self.added_tools:
            lines.append("added tools: " + ", ".join(self.added_tools))
        if self.removed_tools:
            lines.append("removed tools: " + ", ".join(self.removed_tools))
        if not self.added_tools and not self.removed_tools:
            lines.append("tools: unchanged")
        return "\n".join(lines)


def _failed(records: list[AgentRecord]) -> int:
    return sum(1 for record in records if record.outcome.value == "error")


def diff_sessions(store: RecordStore, a: str, b: str) -> SessionDiff:
    """Compute the structural diff between sessions ``a`` and ``b``."""
    records_a = replay_session(store, a)
    records_b = replay_session(store, b)
    counts_a = Counter(record.tool.name for record in records_a)
    counts_b = Counter(record.tool.name for record in records_b)
    added = tuple(sorted(set(counts_b) - set(counts_a)))
    removed = tuple(sorted(set(counts_a) - set(counts_b)))
    environment_a = environment_fingerprint(records_a)
    environment_b = environment_fingerprint(records_b)
    return SessionDiff(
        a=a,
        b=b,
        records_a=len(records_a),
        records_b=len(records_b),
        failed_a=_failed(records_a),
        failed_b=_failed(records_b),
        added_tools=added,
        removed_tools=removed,
        state_a=session_state(records_a).state,
        state_b=session_state(records_b).state,
        environment_a=environment_a,
        environment_b=environment_b,
        environment_changes=tuple(environment_delta(environment_a, environment_b)),
    )
