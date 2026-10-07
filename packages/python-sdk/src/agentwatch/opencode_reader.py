"""OpenCode transcript reader (M27 LOG-1, PRD 45).

OpenCode (``sst/opencode``, MIT) writes each session under its data directory
(``~/.local/share/opencode/storage``; ``OPENCODE_STORAGE_DIR`` override):

    storage/session/info/<sessionID>.json
    storage/session/message/<sessionID>/<messageID>.json
    storage/session/part/<sessionID>/<messageID>/<partID>.json

Tool parts (SDK ``ToolPart``) carry ``{type:"tool", tool, callID,
state:{status,input,output,error,time:{start,end}}}``. This reader turns each
tool part into records through the same redaction path as live capture (DD-06),
read-only, with ``producer: import`` — the ``log-read`` capture level.

Foreign content is untrusted (ADR-0024): the reader only parses; it never spawns
a shell or evaluates content.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

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
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping
from agentwatch.store import RecordStore

HARNESS_ID = "opencode"
OPENCODE_PRODUCER = Producer(kind=ProducerKind.IMPORT, name=HARNESS_ID)

_ACTIVE = frozenset({"pending", "running"})
_ENDED = frozenset({"completed", "error"})

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class OpenCodeReaderError(ValueError):
    """Raised when a storage directory cannot be read."""


@dataclass(frozen=True)
class OpenCodeRead:
    """Outcome of reading an OpenCode storage tree (skips reported, never silent)."""

    records: list[AgentRecord]
    sessions: int
    skipped: int = 0
    dangling: int = 0


@dataclass
class _State:
    session_id: str
    project: str | None = None
    version: str | None = None
    model: str | None = None
    seen: set[tuple[str, str, str]] = field(default_factory=set)


def default_storage_dir() -> Path:
    """The OpenCode storage directory (env override, else the platform default)."""
    import os

    override = os.environ.get("OPENCODE_STORAGE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "opencode" / "storage"


def _ms(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return None


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _capture(raw: Any, cfg: RedactionConfig | None) -> tuple[dict[str, Any] | None, Any]:
    if not isinstance(raw, Mapping):
        return None, None
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, None
    return cast("dict[str, Any]", _redact(raw, cfg)), _PRIVACY_MAP[cfg.mode]


def _load(path: Path) -> Mapping[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, Mapping) else None


def _record(
    state: _State,
    *,
    name: str,
    step_type: StepType,
    outcome: Outcome,
    at: datetime,
    ended_at: datetime | None = None,
    span_id: str | None = None,
    arguments: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    privacy_mode: RecordPrivacyMode | None = None,
    security_event: SecurityEvent | None = None,
) -> AgentRecord:
    tool_kwargs: dict[str, Any] = {"name": name}
    if arguments is not None:
        tool_kwargs["arguments"] = arguments
    if response is not None:
        tool_kwargs["response"] = response
    if privacy_mode is not None:
        tool_kwargs["privacy_mode"] = privacy_mode
    return AgentRecord(
        session_id=state.session_id,
        agent=AgentIdentity(identity=HARNESS_ID, version=state.version, model_version=state.model),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=at,
        harness=HARNESS_ID,
        producer=OPENCODE_PRODUCER,
        trace_id=state.session_id,
        span_id=span_id,
        project=state.project,
        ended_at=ended_at,
        step_type=step_type,
        security_event=security_event,
    )


def _emit(state: _State, record: AgentRecord, out: list[AgentRecord]) -> int:
    step = record.step_type.value if record.step_type else ""
    key = (record.span_id or "", record.tool.name, step)
    if key in state.seen:
        return 1
    state.seen.add(key)
    out.append(record)
    return 0


def _tool_records(
    part: Mapping[str, Any],
    state: _State,
    *,
    redaction: RedactionConfig | None,
) -> tuple[list[AgentRecord], bool]:
    """Records for one tool ``Part``; boolean = dangling (no terminal state)."""
    tool = part.get("tool")
    call_id = part.get("callID")
    status = part.get("state")
    status_map = status if isinstance(status, Mapping) else {}
    status_name = status_map.get("status")
    if not isinstance(tool, str) or not tool:
        return [], False
    span_id = str(call_id) if isinstance(call_id, str) and call_id else None
    times = status_map.get("time")
    times = times if isinstance(times, Mapping) else {}
    started = _ms(times.get("start")) or datetime.now(timezone.utc)
    ended = _ms(times.get("end"))

    inputs = status_map.get("input")
    masked_inputs, input_kinds = redact_mapping(inputs)
    _unused, input_captured, input_privacy, input_event = _content_pair(
        masked_inputs, input_kinds, redaction, tool, started
    )
    act = _record(
        state,
        name=tool,
        step_type=StepType.ACT,
        outcome=Outcome.OK,
        at=started,
        span_id=span_id,
        arguments=input_captured,
        privacy_mode=input_privacy,
        security_event=input_event,
    )
    records = [act]
    if status_name in _ENDED:
        failed = status_name == "error"
        body: Any = (
            {"error": status_map.get("error")} if failed else {"output": status_map.get("output")}
        )
        masked_body, body_kinds = redact_mapping(body)
        _u, body_captured, body_privacy, body_event = _content_pair(
            masked_body, body_kinds, redaction, tool, ended or started
        )
        records.append(
            _record(
                state,
                name=tool,
                step_type=StepType.OBSERVE,
                outcome=Outcome.ERROR if failed else Outcome.OK,
                at=started,
                ended_at=ended,
                span_id=span_id,
                response=body_captured,
                privacy_mode=body_privacy,
                security_event=body_event,
            )
        )
        return records, False
    return records, status_name in _ACTIVE or status_name is None


def _content_pair(
    masked: Any,
    kinds: tuple[str, ...],
    redaction: RedactionConfig | None,
    tool: str,
    at: datetime,
) -> tuple[Any, dict[str, Any] | None, Any, SecurityEvent | None]:
    captured, privacy = _capture(masked, redaction)
    event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=at,
            emitter="agentwatch",
            tool=tool,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )
    return None, captured, privacy, event


def read_storage(root: Path | str, *, redaction: RedactionConfig | None = None) -> OpenCodeRead:
    """Read an OpenCode storage tree into records (read-only, fail-soft per file)."""
    base = Path(root)
    storage = base / "storage" if (base / "storage").is_dir() else base
    info_dir = storage / "session" / "info"
    part_dir = storage / "session" / "part"
    if not info_dir.is_dir() and not part_dir.is_dir():
        raise OpenCodeReaderError(f"not an OpenCode storage tree: {root}")

    sessions: dict[str, Mapping[str, Any]] = {}
    for path in sorted(info_dir.glob("*.json")) if info_dir.is_dir() else []:
        info = _load(path)
        session_id = info.get("id") if isinstance(info, Mapping) else None
        if isinstance(session_id, str) and session_id:
            sessions[session_id] = info if isinstance(info, Mapping) else {}

    records: list[AgentRecord] = []
    skipped = 0
    dangling = 0
    duplicates = 0
    for part_path in sorted(part_dir.glob("*/*/*.json")) if part_dir.is_dir() else []:
        part = _load(part_path)
        if part is None or part.get("type") != "tool":
            skipped += 1
            continue
        session_id = part.get("sessionID")
        session_id = session_id if isinstance(session_id, str) and session_id else "unknown"
        info = sessions.get(session_id, {})
        model = info.get("model")
        state = _State(
            session_id=session_id,
            project=info.get("directory") if isinstance(info.get("directory"), str) else None,
            version=info.get("version") if isinstance(info.get("version"), str) else None,
            model=model.get("id") if isinstance(model, Mapping) else None,
        )
        part_records, is_dangling = _tool_records(part, state, redaction=redaction)
        if is_dangling:
            dangling += 1
        for record in part_records:
            duplicates += _emit(state, record, records)

    return OpenCodeRead(
        records=records, sessions=len(sessions), skipped=skipped, dangling=dangling
    )


@dataclass(frozen=True)
class OpenCodeIngestStats:
    """Outcome of ingesting an OpenCode storage tree."""

    records: int
    sessions: int
    skipped: int
    duplicates: int
    dangling: int


def ingest_storage(
    root: Path | str, store: RecordStore, *, redaction: RedactionConfig | None = None
) -> OpenCodeIngestStats:
    """Read an OpenCode storage tree into ``store`` (idempotent on span/step)."""
    read = read_storage(root, redaction=redaction)
    existing = {
        (record.session_id, record.span_id, record.step_type) for record in store.records()
    }
    appended = duplicates = skipped = 0
    for record in read.records:
        key = (record.session_id, record.span_id, record.step_type)
        if record.span_id is not None and key in existing:
            duplicates += 1
            continue
        try:
            store.append(record)
        except ValueError:
            skipped += 1
        else:
            appended += 1
            existing.add(key)
    return OpenCodeIngestStats(
        records=appended,
        sessions=read.sessions,
        skipped=read.skipped + skipped,
        duplicates=duplicates,
        dangling=read.dangling,
    )


__all__ = [
    "HARNESS_ID",
    "OPENCODE_PRODUCER",
    "OpenCodeIngestStats",
    "OpenCodeRead",
    "OpenCodeReaderError",
    "default_storage_dir",
    "ingest_storage",
    "read_storage",
]
