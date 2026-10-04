"""Session behavior fingerprint (M17 S7, PRD 33).

A deterministic digest over the normalized action sequence — ordered
``(server, tool, step_type, outcome)`` tuples, **arguments excluded**. Two runs
that did the same thing share a digest even with different session ids; an added
tool changes it. The normalization is published and versioned: the digest is
``bd1:<sha256>`` so it can be tightened later without silently redefining old
values.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from agentwatch.records import AgentRecord
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore

DIGEST_VERSION = "bd1"

# Marker/internal records are not agent behavior.
_INTERNAL_TOOLS = frozenset(
    {
        "recording-gap",
        "hook-error",
        "session-purge",
        "operator-note",
        "store-access",
        "harness-drift",
        "session-usage",
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


def action_tuple(record: AgentRecord) -> tuple[str, str, str, str] | None:
    """The normalized ``(server, name, step_type, outcome)`` for one record, or None."""
    if record.tool.name in _INTERNAL_TOOLS:
        return None
    server = (record.tool.server or "").lower()
    step = record.step_type.value if record.step_type is not None else ""
    return (server, record.tool.name.lower(), step, record.outcome.value.lower())


def action_sequence(records: Sequence[AgentRecord]) -> tuple[tuple[str, str, str, str], ...]:
    """The ordered normalized action tuples (arguments excluded)."""
    actions: list[tuple[str, str, str, str]] = []
    for record in records:
        action = action_tuple(record)
        if action is not None:
            actions.append(action)
    return tuple(actions)


def behavior_digest(records: Iterable[AgentRecord]) -> str:
    """A versioned digest over an ordered record sequence (``bd1:<sha256>``)."""
    sequence = action_sequence(list(records))
    canonical = "\n".join("|".join(parts) for parts in sequence)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{DIGEST_VERSION}:{digest}"


def session_behavior_digest(store: RecordStore, session_id: str) -> str:
    """The behavior digest for one session (replayed order)."""
    return behavior_digest(replay_session(store, session_id))


def group_sessions_by_behavior(store: RecordStore) -> dict[str, tuple[str, ...]]:
    """Group every session by its behavior digest, sessions in first-seen order."""
    order: list[str] = []
    seen: set[str] = set()
    for record in store.records():
        if record.session_id in seen or record.tool.name in _INTERNAL_TOOLS:
            continue
        seen.add(record.session_id)
        order.append(record.session_id)
    groups: dict[str, list[str]] = {}
    for session_id in order:
        digest = session_behavior_digest(store, session_id)
        groups.setdefault(digest, []).append(session_id)
    return {digest: tuple(sessions) for digest, sessions in groups.items()}


def render_behavior_groups(groups: dict[str, tuple[str, ...]]) -> str:
    """Render behavior groups as ``DIGEST  n  session,session`` lines."""
    lines = ["BEHAVIOR\tSESSIONS\tCOUNT"]
    for digest, sessions in groups.items():
        lines.append(f"{digest}\t{','.join(sessions)}\t{len(sessions)}")
    return "\n".join(lines)


__all__ = [
    "DIGEST_VERSION",
    "action_sequence",
    "action_tuple",
    "behavior_digest",
    "group_sessions_by_behavior",
    "render_behavior_groups",
    "session_behavior_digest",
]
