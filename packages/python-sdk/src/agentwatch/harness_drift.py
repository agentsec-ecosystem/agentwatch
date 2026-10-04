"""Harness-drift canary from real traffic (M16 S19, #240).

N4 tracks harness versions from release metadata and G4 preflights at install;
both learn about a change *after* it is published. The failure that matters is
silent: the harness renames a field, adds a hook phase, or changes a payload, and
agentwatch keeps exiting 0 while recording less. The adapter sees the truth on
every event and, until now, discarded it.

This module compares a live frame against the fields the Claude Code adapter
knows. It records a **metadata-only** ``harness-drift`` observation naming the
unrecognized *fields* (never values) and harness version. Field names from an
untrusted payload are themselves untrusted, so they are allow-listed to safe
characters, length-capped, and cardinality-capped. Observations are debounced:
a field is reported once per session (and no more than once per debounce window
across sessions), and additive fields are framed as *additive*, not *broken*.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

HARNESS_DRIFT_TOOL = "harness-drift"

# D-31.3: report a given (harness, field) at most once per hour across sessions;
# within one session it is reported at most once.
DEFAULT_DEBOUNCE_SECONDS = 3600.0

MAX_FIELDS = 16
MAX_FIELD_NAME = 64

# Hook phases the Claude Code adapter understands. Anything else is drift.
KNOWN_PHASES = frozenset({"pre", "post", "denied", "prompt", "session-start", "session-end"})

# Top-level fields the Claude Code adapter consumes from an event payload. A key
# outside this set is "additive" by default: harnesses add fields routinely.
KNOWN_EVENT_FIELDS = frozenset(
    {
        "session_id",
        "sessionId",
        "tool",
        "tool_name",
        "tool_input",
        "tool_response",
        "tool_use_id",
        "tool_call_id",
        "trace_id",
        "cwd",
        "error",
        "started_at",
        "ended_at",
        "duration_ms",
        "timestamp",
        "reason",
        "source",
        "parent_session_id",
        "source_session_id",
        "agent",
        "agent_id",
        "agent_type",
        "prompt_version",
        "prompt",
        "model",
        "transcript_path",
    }
)

_FIELD_RE = re.compile(r"[^A-Za-z0-9_.-]")


def sanitize_field_name(name: object) -> str | None:
    """Allow-list a field name to safe characters, cap its length, or reject it."""
    if not isinstance(name, str):
        return None
    cleaned = _FIELD_RE.sub("", name)[:MAX_FIELD_NAME]
    return cleaned or None


def unknown_event_fields(event: object) -> tuple[str, ...]:
    """Unrecognized top-level field *names* in an event payload (names only).

    Returns a sorted, de-duplicated, allow-listed, cardinality-capped tuple. It
    never reads or returns a value, so an untrusted payload cannot smuggle
    content through the canary.
    """
    if not isinstance(event, Mapping):
        return ()
    names: set[str] = set()
    for key in event:
        clean = sanitize_field_name(key)
        if clean is None or key in KNOWN_EVENT_FIELDS or clean in KNOWN_EVENT_FIELDS:
            continue
        names.add(clean)
    return tuple(sorted(names)[:MAX_FIELDS])


def is_unknown_phase(phase: object) -> bool:
    """Whether ``phase`` is a hook phase the adapter does not understand."""
    return isinstance(phase, str) and phase not in KNOWN_PHASES


@dataclass(frozen=True)
class DriftEvent:
    """One debounced drift observation, ready to store."""

    harness: str
    session_id: str
    fields: tuple[str, ...]
    phase: str | None
    additive: bool
    at: datetime


class DriftTracker:
    """Debounce drift observations so additive churn does not flood the chain."""

    def __init__(
        self,
        *,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
        seed: Iterable[DriftEvent] = (),
    ) -> None:
        self.debounce_seconds = debounce_seconds
        # (harness, field) -> last time it was reported (cross-session debounce).
        self._field_seen: dict[tuple[str, str], datetime] = {}
        # (harness, session, field) already reported in that session.
        self._session_seen: set[tuple[str, str, str]] = set()
        # (harness, phase) already reported.
        self._phase_seen: set[tuple[str, str]] = set()
        for event in seed:
            self._remember(event)

    def _remember(self, event: DriftEvent) -> None:
        for field in event.fields:
            self._field_seen[(event.harness, field)] = event.at
            self._session_seen.add((event.harness, event.session_id, field))
        if event.phase is not None:
            self._phase_seen.add((event.harness, event.phase))

    def observe(
        self,
        *,
        harness: str,
        session_id: str,
        event: object,
        phase: object,
        at: datetime | None = None,
    ) -> DriftEvent | None:
        """Return a drift observation when something new is seen, else ``None``."""
        moment = at or datetime.now(timezone.utc)
        fresh: list[str] = []
        for field in unknown_event_fields(event):
            if (harness, session_id, field) in self._session_seen:
                continue
            last = self._field_seen.get((harness, field))
            if last is not None and (moment - last).total_seconds() < self.debounce_seconds:
                continue
            fresh.append(field)
        unknown_phase: str | None = None
        if is_unknown_phase(phase) and (harness, str(phase)) not in self._phase_seen:
            unknown_phase = str(phase)
        if not fresh and unknown_phase is None:
            return None
        observation = DriftEvent(
            harness=harness,
            session_id=session_id,
            fields=tuple(fresh),
            phase=unknown_phase,
            # A new phase is a real break; an added field is routine.
            additive=unknown_phase is None,
            at=moment,
        )
        self._remember(observation)
        return observation


def harness_drift_record(
    observation: DriftEvent, *, harness_version: str | None = None
) -> AgentRecord:
    """Render a drift observation as a metadata-only ``harness-drift`` record."""
    arguments: dict[str, object] = {
        "harness": observation.harness,
        "fields": list(observation.fields),
        "additive": observation.additive,
    }
    if observation.phase is not None:
        arguments["phase"] = observation.phase
    if harness_version:
        arguments["harness_version"] = sanitize_field_name(harness_version) or ""
    return AgentRecord(
        session_id=observation.session_id,
        agent=AgentIdentity(identity=observation.harness),
        tool=ToolCall(
            name=HARNESS_DRIFT_TOOL,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=observation.at,
        harness=observation.harness,
        producer=MARKER_PRODUCER,
        trace_id=observation.session_id,
    )


@dataclass(frozen=True)
class DriftObservation:
    """One stored ``harness-drift`` observation, for read-side reporting."""

    harness: str
    fields: tuple[str, ...]
    phase: str | None
    additive: bool
    harness_version: str | None
    session_id: str
    at: datetime
    seq: int


def harness_drift_observations(store: RecordStore) -> list[DriftObservation]:
    """Every stored drift observation, in store order."""
    observations: list[DriftObservation] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != HARNESS_DRIFT_TOOL:
            continue
        arguments = record.tool.arguments or {}
        raw_fields = arguments.get("fields")
        fields = tuple(str(item) for item in raw_fields) if isinstance(raw_fields, list) else ()
        phase = arguments.get("phase")
        version = arguments.get("harness_version")
        observations.append(
            DriftObservation(
                harness=str(arguments.get("harness", record.harness or "")),
                fields=fields,
                phase=str(phase) if isinstance(phase, str) else None,
                additive=bool(arguments.get("additive", True)),
                harness_version=str(version) if isinstance(version, str) and version else None,
                session_id=record.session_id,
                at=record.started_at,
                seq=entry.seq,
            )
        )
    return observations


def seed_events(store: RecordStore) -> list[DriftEvent]:
    """Rebuild :class:`DriftEvent`s from stored observations, so a restarted
    daemon does not re-report drift it already recorded."""
    return [
        DriftEvent(
            harness=observation.harness,
            session_id=observation.session_id,
            fields=observation.fields,
            phase=observation.phase,
            additive=observation.additive,
            at=observation.at,
        )
        for observation in harness_drift_observations(store)
    ]
