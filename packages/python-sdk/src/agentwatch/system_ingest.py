"""System-effects ingest: AgentSight/Tracee-shaped system events (M29 SYS-1, #366).

``impact`` stops at the tool-call layer. This module ingests the *system-effects*
layer below it — AgentSight/Tracee-shaped process-exec and network-connect events
joined to sessions by **process lineage and time-window** — so a spawned child
process's network contacts become blast-radius facts labeled
``source: system-ingest``.

Honesty rules (the lower layer is foreign and never silently trusted):

* **Linux, opt-in, declared gap elsewhere.** AgentSight/Tracee probes exist only
  on Linux; agentwatch does not build probes (Linux-root eBPF violates our
  portability/trust posture). This is a *reader* for a foreign stream and refuses
  to run without explicit ``opted_in=True``.
* **Labeled.** Every record carries ``environment.source == "system-ingest"`` and
  a ``producer.kind=ingest``/``name=system-ingest``; it is distinguished from the
  hook truth (S11 integrity distinction).
* **No silent attribution.** A record whose process lineage is not owned by
  exactly one known session is filed under ``unjoined:system-ingest`` — never
  guessed into a session's blast radius.
* **Redact before store.** Foreign content runs through the secrets pipeline
  before storage (DD-06); unmappable input is quarantined with a reason (B4).
* **Published false-join precision.** :data:`PUBLISHED_PRECISION` is measured over
  the committed synthetic lineage corpus, never asserted from a real capture.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch.ingest import IngestProblem, IngestStats
from agentwatch.quarantine import QuarantineLog
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
    validate_record,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping
from agentwatch.store import RecordStore

HARNESS_ID = "system-ingest"
SYSTEM_INGEST_PRODUCER = Producer(kind=ProducerKind.INGEST, name=HARNESS_ID)
UNJOINED_SESSION = "unjoined:system-ingest"

# The Linux-only lower layer is a declared gap everywhere else (PRD 45 §SYS-1).
SUPPORTED_PLATFORMS: frozenset[str] = frozenset({"linux"})

# Published from tests/fixtures/system-ingest/lineage-corpus.json (synthetic).
PUBLISHED_PRECISION: dict[str, Any] = {
    "corpus": "system-ingest-lineage-corpus/1",
    "precision": 1.0,
    "recall": 1.0,
}

DEFAULT_WINDOW_SLACK_SECONDS = 300.0

_PROCESS_TYPE = "system:process-exec"
_NETWORK_TYPE = "system:network-connect"
_PROCESS_KINDS = frozenset(
    {"process", "process_exec", "process_execve", "process_fork", "exec", "execve"}
)
_NETWORK_KINDS = frozenset(
    {"network", "network_connect", "net_connect", "connect", "security_socket_connect"}
)

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class SystemIngestError(ValueError):
    """Raised when a foreign system event cannot be mapped."""


class SystemIngestNotOptedInError(SystemIngestError):
    """Raised when the Linux-only layer is ingested without explicit opt-in."""


@dataclass(frozen=True)
class SystemEvent:
    """One normalized foreign system event (process or network)."""

    kind: str  # _PROCESS_TYPE | _NETWORK_TYPE
    pid: int
    ppid: int | None
    name: str | None
    at: datetime
    target: str | None = None
    exe: str | None = None
    session_hint: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionIndex:
    """Which session (if any) owns a pid, plus each session's time window.

    A pid owned by more than one session is **ambiguous** and never joins
    (precision over recall); a session with no recorded window has no time bound.
    """

    pid_owner: Mapping[int, str] = field(default_factory=dict)
    ambiguous_pids: frozenset[int] = frozenset()
    windows: Mapping[str, tuple[datetime | None, datetime | None]] = field(
        default_factory=dict
    )
    slack_seconds: float = DEFAULT_WINDOW_SLACK_SECONDS

    @classmethod
    def from_pid_map(cls, mapping: Mapping[str, Iterable[int]]) -> SessionIndex:
        owners: dict[int, set[str]] = {}
        windows: dict[str, tuple[datetime | None, datetime | None]] = {}
        for session, pids in mapping.items():
            windows[session] = (None, None)
            for pid in pids:
                owners.setdefault(int(pid), set()).add(session)
        owner = {pid: next(iter(s)) for pid, s in owners.items() if len(s) == 1}
        ambiguous = frozenset(pid for pid, s in owners.items() if len(s) > 1)
        return cls(pid_owner=owner, ambiguous_pids=ambiguous, windows=windows)

    @classmethod
    def from_records(
        cls, records: Iterable[AgentRecord], *, slack_seconds: float = DEFAULT_WINDOW_SLACK_SECONDS
    ) -> SessionIndex:
        owners: dict[int, set[str]] = {}
        windows: dict[str, tuple[datetime, datetime]] = {}
        for record in records:
            environment = record.environment or {}
            pid = environment.get("pid")
            if isinstance(pid, int) and not isinstance(pid, bool):
                owners.setdefault(pid, set()).add(record.session_id)
            start = record.started_at
            end = record.ended_at or record.started_at
            lo, hi = windows.get(record.session_id, (start, end))
            windows[record.session_id] = (
                min(lo, start),
                max(hi, end),
            )
        owner = {pid: next(iter(s)) for pid, s in owners.items() if len(s) == 1}
        ambiguous = frozenset(pid for pid, s in owners.items() if len(s) > 1)
        return cls(
            pid_owner=owner,
            ambiguous_pids=ambiguous,
            windows={s: (lo, hi) for s, (lo, hi) in windows.items()},
            slack_seconds=slack_seconds,
        )

    def owner_for(self, pid: int) -> str | None:
        if pid in self.ambiguous_pids:
            return None
        return self.pid_owner.get(pid)

    def in_window(self, session: str, at: datetime) -> bool:
        window = self.windows.get(session)
        if window is None:
            return True
        lo, hi = window
        if lo is None or hi is None:
            return True
        slack = timedelta(seconds=self.slack_seconds)
        return lo - slack <= at <= hi + slack


@dataclass(frozen=True)
class JoinPrecision:
    """Measured lineage false-join precision/recall over a labeled corpus."""

    total: int
    true_joins: int
    false_joins: int
    missed: int

    @property
    def precision(self) -> float:
        denom = self.true_joins + self.false_joins
        return self.true_joins / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.true_joins + self.missed
        return self.true_joins / denom if denom else 1.0


def join_precision(
    predicted: Sequence[str | None], truth: Sequence[str | None]
) -> JoinPrecision:
    """Compare predicted joins (``None`` = unjoined) against ground truth."""
    true_joins = false_joins = missed = 0
    for guess, actual in zip(predicted, truth, strict=True):
        if guess is not None:
            if guess == actual:
                true_joins += 1
            else:
                false_joins += 1
        elif actual is not None:
            missed += 1
    return JoinPrecision(
        total=len(predicted),
        true_joins=true_joins,
        false_joins=false_joins,
        missed=missed,
    )


def platform_covered(platform: str) -> bool:
    """Whether the live system-effects layer is covered on ``platform``."""
    return platform in SUPPORTED_PLATFORMS


def is_system_ingest_record(record: AgentRecord) -> bool:
    """Whether a record came from the foreign system-effects layer."""
    environment = record.environment or {}
    return (
        environment.get("source") == HARNESS_ID
        or record.harness == HARNESS_ID
    )


# ---------------------------------------------------------------------------
# Parsing (AgentSight-shaped and Tracee-shaped)
# ---------------------------------------------------------------------------


def _timestamp(value: Any) -> datetime:
    if isinstance(value, str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise SystemIngestError(f"invalid timestamp {value!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1e9 if value > 1e12 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _first(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _event_kind(item: Mapping[str, Any]) -> str:
    raw = str(_first(item, "type", "eventName", "event", "kind") or "").lower()
    if raw in _PROCESS_KINDS:
        return _PROCESS_TYPE
    if raw in _NETWORK_KINDS:
        return _NETWORK_TYPE
    raise SystemIngestError(f"unmappable system event kind {raw!r}")


def _parse_event(item: Any) -> SystemEvent:
    if not isinstance(item, Mapping):
        raise SystemIngestError("system event is not an object")
    kind = _event_kind(item)
    pid = _int(_first(item, "pid", "processId", "process_id"))
    if pid is None:
        raise SystemIngestError("system event has no pid")
    ppid = _int(_first(item, "ppid", "parentProcessId", "parent_process_id"))
    name = _first(item, "comm", "processName", "process_name", "exe")
    name = str(name) if isinstance(name, str) and name else None
    at = _timestamp(_first(item, "timestamp", "time", "ts", "eventTime"))
    hint = _first(item, "session_id", "sessionId")
    session_hint = str(hint) if isinstance(hint, str) and hint else None
    if kind == _PROCESS_TYPE:
        raw_exe = _first(item, "exe", "cmdline", "command")
        if isinstance(raw_exe, list):
            exe: str | None = " ".join(str(part) for part in raw_exe)
        else:
            exe = str(raw_exe) if isinstance(raw_exe, str) and raw_exe else name
        return SystemEvent(
            kind=kind,
            pid=pid,
            ppid=ppid,
            name=name,
            at=at,
            exe=exe,
            session_hint=session_hint,
            raw=item,
        )
    address = _first(item, "daddr", "dstIP", "dst_ip", "saddr", "addr")
    port = _int(_first(item, "dport", "dstPort", "dst_port", "port"))
    target = None
    if isinstance(address, str) and address:
        target = f"{address}:{port}" if port is not None else address
    return SystemEvent(
        kind=kind,
        pid=pid,
        ppid=ppid,
        name=name,
        at=at,
        target=target,
        session_hint=session_hint,
        raw=item,
    )


def parse_system_events(
    payload: Any, *, source: str = HARNESS_ID
) -> tuple[list[SystemEvent], list[IngestProblem]]:
    """Parse an AgentSight/Tracee-shaped payload into normalized events.

    Accepts a lone event, a list of events, a ``{"events": [...]}`` envelope, or
    a JSON string. Anything unmappable is a problem (never dropped silently).
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            return [], [IngestProblem(source, f"invalid JSON: {exc}")]
    items: list[Any]
    if isinstance(payload, Mapping) and isinstance(payload.get("events"), list):
        items = list(payload["events"])
    elif isinstance(payload, list):
        items = list(payload)
    elif isinstance(payload, Mapping):
        items = [payload]
    else:
        return [], [IngestProblem(source, "system payload is not events/list/object")]

    events: list[SystemEvent] = []
    problems: list[IngestProblem] = []
    for index, item in enumerate(items):
        try:
            events.append(_parse_event(item))
        except (SystemIngestError, KeyError, TypeError, ValueError) as exc:
            problems.append(IngestProblem(f"{source}#{index}", f"unmappable system event: {exc}"))
    return events, problems


# ---------------------------------------------------------------------------
# Lineage join
# ---------------------------------------------------------------------------


def _parent_map(events: Iterable[SystemEvent]) -> dict[int, int]:
    parents: dict[int, int] = {}
    for event in events:
        if event.ppid is not None:
            parents[event.pid] = event.ppid
    return parents


def _owner_via_lineage(
    event: SystemEvent, parents: Mapping[int, int], sessions: SessionIndex
) -> str | None:
    """The single session that owns this event's process lineage, or ``None``."""
    seen: set[int] = set()
    owners: set[str] = set()
    cursor: int | None = event.pid
    while cursor is not None and cursor not in seen:
        seen.add(cursor)
        owner = sessions.owner_for(cursor)
        if owner is not None:
            owners.add(owner)
        cursor = parents.get(cursor)
    return next(iter(owners)) if len(owners) == 1 else None


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _captured(
    arguments: dict[str, Any], cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    # Secrets are masked before any content is stored (DD-06), then the capture
    # mode (truncated/hashed/full) is applied.
    masked, _ = redact_mapping(arguments)
    return _redact(masked, cfg), _PRIVACY_MAP[cfg.mode]


def _record(
    event: SystemEvent,
    *,
    session: str | None,
    join: str,
    redaction: RedactionConfig | None,
    span_id: str,
) -> AgentRecord:
    masked, kinds = redact_mapping(event.raw)
    security_event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=event.at,
            emitter="agentwatch",
            tool=event.kind,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )

    tool_kwargs: dict[str, Any] = {"name": event.kind}
    if event.kind == _NETWORK_TYPE:
        # The destination is structural truth, not captured content: it stays on
        # the record so the blast radius is honest even in metadata-only mode.
        tool_kwargs["server"] = event.target or "unknown"
        raw_arguments = {"target": event.target}
    else:
        raw_arguments = {"exe": event.exe}
    captured, privacy_mode = _captured(raw_arguments, redaction)
    if captured is not None:
        tool_kwargs["arguments"] = captured
        tool_kwargs["privacy_mode"] = privacy_mode

    environment: dict[str, Any] = {
        "source": HARNESS_ID,
        "pid": event.pid,
        "ppid": event.ppid,
        "joined": session is not None,
        "join": join,
    }
    if event.session_hint is not None:
        # Foreign annotation; recorded for triage, never used to attribute (it is
        # the lower layer telling us the answer).
        environment["foreign_session_hint"] = event.session_hint

    record = AgentRecord(
        session_id=session or UNJOINED_SESSION,
        agent=AgentIdentity(identity=event.name or HARNESS_ID),
        tool=ToolCall(**tool_kwargs),
        outcome=Outcome.OK,
        started_at=event.at,
        harness=HARNESS_ID,
        producer=SYSTEM_INGEST_PRODUCER,
        trace_id=session or UNJOINED_SESSION,
        span_id=span_id,
        step_type=StepType.OBSERVE,
        environment=environment,
        security_event=security_event,
    )
    validate_record(record.to_dict())
    return record


def transcode_system_ingest(
    payload: Any,
    *,
    source: str = HARNESS_ID,
    opted_in: bool = False,
    sessions: SessionIndex | None = None,
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode a foreign system-event payload into labeled records + problems.

    Refuses to run without ``opted_in=True`` (Linux-only opt-in layer). An event
    whose lineage is not owned by exactly one known session is filed under
    ``unjoined:system-ingest`` (never silently attributed).
    """
    if not opted_in:
        raise SystemIngestNotOptedInError(
            "system-effects ingest is Linux-only and opt-in; pass opted_in=True"
        )
    events, problems = parse_system_events(payload, source=source)
    index = sessions or SessionIndex()
    parents = _parent_map(events)
    records: list[AgentRecord] = []
    for event in events:
        owner = _owner_via_lineage(event, parents, index)
        if owner is None:
            join = "unowned"
        elif not index.in_window(owner, event.at):
            join = "outside-window"
            owner = None
        else:
            join = "lineage"
        span_id = f"system-ingest:{event.pid}:{event.kind}:{int(event.at.timestamp())}"
        records.append(
            _record(event, session=owner, join=join, redaction=redaction, span_id=span_id)
        )
    return records, problems


def run_system_ingest(
    paths: Iterable[Path],
    store: RecordStore,
    *,
    opted_in: bool,
    sessions: SessionIndex,
    quarantine: QuarantineLog | None = None,
    redaction: RedactionConfig | None = None,
    source: str | None = None,
) -> IngestStats:
    """Ingest system-event files into ``store``; report counts + problems.

    Opt-in is enforced both here and in :func:`transcode_system_ingest`; problems
    are quarantined (when a log is given) and counted, never dropped silently.
    Idempotent on ``span_id`` so re-ingesting the same stream does not inflate.
    """
    if not opted_in:
        raise SystemIngestNotOptedInError(
            "system-effects ingest is Linux-only and opt-in; pass opted_in=True"
        )
    files = 0
    records = 0
    skipped = 0
    duplicates = 0
    problems: list[IngestProblem] = []
    existing = {(record.session_id, record.span_id) for record in store.records()}
    for path in paths:
        files += 1
        name = source or path.stem
        try:
            text = path.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            problems.append(IngestProblem(name, f"unreadable: {exc}"))
            continue
        found, probs = transcode_system_ingest(
            text, source=name, opted_in=opted_in, sessions=sessions, redaction=redaction
        )
        problems.extend(probs)
        if quarantine is not None:
            for problem in probs:
                quarantine.add(text, reason=problem.reason)
        for record in found:
            key = (record.session_id, record.span_id)
            if key in existing:
                duplicates += 1
                continue
            try:
                store.append(record)
            except ValueError:
                skipped += 1
            else:
                records += 1
                existing.add(key)
    return IngestStats(
        files=files,
        records=records,
        skipped=skipped,
        duplicates=duplicates,
        problems=tuple(problems),
    )


__all__ = [
    "DEFAULT_WINDOW_SLACK_SECONDS",
    "HARNESS_ID",
    "PUBLISHED_PRECISION",
    "SUPPORTED_PLATFORMS",
    "SYSTEM_INGEST_PRODUCER",
    "UNJOINED_SESSION",
    "JoinPrecision",
    "SessionIndex",
    "SystemEvent",
    "SystemIngestError",
    "SystemIngestNotOptedInError",
    "is_system_ingest_record",
    "join_precision",
    "parse_system_events",
    "platform_covered",
    "run_system_ingest",
    "transcode_system_ingest",
]
