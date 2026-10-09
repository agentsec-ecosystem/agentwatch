"""Codex CLI rollout reader (M27 COD-1, PRD 42).

Codex writes one session per ``rollout-*.jsonl`` file under
``~/.codex/sessions/YYYY/MM/DD/`` (``.jsonl`` or ``.jsonl.zst``;
``CODEX_HOME``/``CODEX_SESSIONS_DIR`` overridable). Each line is a JSON object
``{"timestamp", "type", "payload"}``; ``payload.type`` distinguishes messages,
tool calls/results, token counts, and compaction. The format is documented and
verified from the ``openai/codex`` source (see
``docs/design/cross-harness-testing.md``).

The reader turns ``function_call``/``function_call_output`` pairs
(``custom_tool_call``, ``local_shell_call``, ``web_search_call``) into records
**through the same redaction path** as live capture (DD-06), dedups the repeated
plaintext Codex emits (F2), and marks an unanswered call as an inferred
``crashed`` end-state (S33).

Untrusted-data rule (ADR-0024): a rollout is attacker-influenced. The reader only
parses; it never spawns a shell, evaluates content, or follows a log path into a
command.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator, Mapping
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
    _parse_iso,
)
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping
from agentwatch.store import RecordStore

HARNESS_ID = "codex-cli"
CODEX_PRODUCER = Producer(kind=ProducerKind.IMPORT, name=HARNESS_ID)

# A session with no completion for this long is a dangling session (S33).
DANGLING_AFTER_MINUTES = 2

_CALL_TYPES = {
    "function_call": None,  # use payload.name
    "custom_tool_call": None,
    "local_shell_call": "shell",
    "web_search_call": "web_search",
}
_OUTPUT_TYPES = frozenset({"function_call_output", "custom_tool_call_output"})

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}


class CodexRolloutError(ValueError):
    """Raised when a rollout file cannot be read (zstd missing, unreadable)."""


@dataclass(frozen=True)
class RolloutRead:
    """Outcome of reading one rollout (skips/duplicates reported, never silent)."""

    records: list[AgentRecord]
    session_id: str | None
    skipped: int = 0
    duplicates: int = 0
    dangling: bool = False
    tokens: int | None = None


@dataclass
class _State:
    session_id: str | None = None
    project: str | None = None
    cli_version: str | None = None
    model: str | None = None
    tokens: int | None = None
    pending: dict[str, tuple[str, datetime]] = field(default_factory=dict)
    seen: set[tuple[str, str, str]] = field(default_factory=set)


def _iter_lines(path: Path) -> Iterator[str]:
    if path.suffix == ".zst":
        yield from _iter_zstd_lines(path)
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        yield from handle


def _iter_zstd_lines(path: Path) -> Iterator[str]:
    module: Any = None
    for name in ("compression.zstd", "zstandard"):  # stdlib 3.14, then the extra
        try:
            module = importlib.import_module(name)
            break
        except ImportError:
            continue
    if module is None:
        raise CodexRolloutError(
            "reading .jsonl.zst requires Python 3.14+ or the 'agentwatch[codex]' extra"
        )
    with module.open(path, "rt", encoding="utf-8") as handle:
        yield from handle


def _time(entry: Mapping[str, Any]) -> datetime:
    raw = entry.get("timestamp")
    if isinstance(raw, str):
        try:
            return _parse_iso(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _arguments(raw: Any) -> dict[str, Any]:
    """Codex serializes tool arguments as a JSON string; parse when possible."""
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        if isinstance(parsed, Mapping):
            return dict(parsed)
        return {"input": parsed}
    return {}


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
        session_id=state.session_id or "unknown",
        agent=AgentIdentity(
            identity=HARNESS_ID, version=state.cli_version, model_version=state.model
        ),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=at,
        harness=HARNESS_ID,
        producer=CODEX_PRODUCER,
        trace_id=state.session_id or "unknown",
        span_id=span_id,
        project=state.project,
        ended_at=ended_at,
        tokens=state.tokens,
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


def _content_pair(
    raw: Any, redaction: RedactionConfig | None, tool: str, at: datetime
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    RecordPrivacyMode | None,
    SecurityEvent | None,
]:
    masked, kinds = redact_mapping(raw)
    captured, privacy = _capture(masked, redaction)
    security_event = (
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
    if captured is not None and privacy is not None:
        return None, captured, privacy, security_event
    return None, None, None, security_event


def read_rollout(path: Path | str, *, redaction: RedactionConfig | None = None) -> RolloutRead:
    """Read one Codex rollout file into records (read-only, fail-soft per line)."""
    rollout = Path(path)
    if not rollout.is_file():
        raise CodexRolloutError(f"no such rollout file: {rollout}")

    state = _State()
    records: list[AgentRecord] = []
    skipped = 0
    duplicates = 0

    for line in _iter_lines(rollout):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(entry, Mapping):
            skipped += 1
            continue
        kind = entry.get("type")
        payload = entry.get("payload")
        payload = payload if isinstance(payload, Mapping) else {}
        at = _time(entry)

        if kind == "session_meta":
            raw_id = payload.get("id")
            if isinstance(raw_id, str) and raw_id:
                state.session_id = raw_id
            cwd = payload.get("cwd")
            if isinstance(cwd, str) and cwd:
                state.project = cwd
            version = payload.get("cli_version")
            if isinstance(version, str) and version:
                state.cli_version = version
        elif kind == "turn_context":
            model = payload.get("model")
            if isinstance(model, str) and model:
                state.model = model
        elif kind == "compacted":
            trigger = payload.get("trigger") or payload.get("reason")
            compacted = _record(
                state,
                name="context-compacted",
                step_type=StepType.OBSERVE,
                outcome=Outcome.OK,
                at=at,
            )
            if isinstance(trigger, str) and trigger:
                compacted = _with_arguments(compacted, {"trigger": trigger})
            duplicates += _emit(state, compacted, records)
        elif kind == "event_msg":
            info = payload.get("info")
            if payload.get("type") == "token_count" and isinstance(info, Mapping):
                total = info.get("total_token_usage")
                if isinstance(total, Mapping):
                    value = total.get("total_tokens")
                    if isinstance(value, int) and not isinstance(value, bool):
                        state.tokens = value
            else:
                skipped += 1
        elif kind == "response_item":
            ptype = payload.get("type")
            if ptype in _CALL_TYPES:
                name = (
                    _CALL_TYPES[ptype]
                    or payload.get("name")
                    or payload.get("tool_name")
                    or "tool"
                )
                name = str(name)
                call_id = payload.get("call_id") or payload.get("id")
                span_id = str(call_id) if isinstance(call_id, str) and call_id else None
                _, captured, privacy, event = _content_pair(
                    _arguments(payload.get("arguments")), redaction, name, at
                )
                record = _record(
                    state,
                    name=name,
                    step_type=StepType.ACT,
                    outcome=Outcome.OK,
                    at=at,
                    span_id=span_id,
                    arguments=captured,
                    privacy_mode=privacy,
                    security_event=event,
                )
                duplicates += _emit(state, record, records)
                if span_id is not None:
                    state.pending[span_id] = (name, at)
            elif ptype in _OUTPUT_TYPES:
                call_id = payload.get("call_id") or payload.get("id")
                span_id = str(call_id) if isinstance(call_id, str) and call_id else None
                pending = state.pending.pop(span_id, None) if span_id is not None else None
                name = pending[0] if pending else "tool"
                started = pending[1] if pending else at
                _, captured, privacy, event = _content_pair(
                    {"output": payload.get("output")}, redaction, name, at
                )
                record = _record(
                    state,
                    name=name,
                    step_type=StepType.OBSERVE,
                    outcome=Outcome.OK,
                    at=started,
                    ended_at=at,
                    span_id=span_id,
                    response=captured,
                    privacy_mode=privacy,
                    security_event=event,
                )
                duplicates += _emit(state, record, records)
            else:
                # message / reasoning / ghost_snapshot / unknown → forward-compat skip.
                skipped += 1
        else:
            # An unknown top-level record type is skipped visibly (forward-compat).
            skipped += 1

    # An unanswered call is an inferred ``crashed`` end-state (S33), never silent.
    dangling = bool(state.pending)
    for span_id, (name, started) in state.pending.items():
        record = _record(
            state,
            name=name,
            step_type=StepType.OBSERVE,
            outcome=Outcome.ERROR,
            at=started,
            span_id=span_id,
        )
        duplicates += _emit(state, record, records)

    return RolloutRead(
        records=records,
        session_id=state.session_id,
        skipped=skipped,
        duplicates=duplicates,
        dangling=dangling,
        tokens=state.tokens,
    )


def _with_arguments(record: AgentRecord, arguments: dict[str, Any]) -> AgentRecord:
    from dataclasses import replace

    return replace(
        record,
        tool=replace(
            record.tool,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
    )


@dataclass(frozen=True)
class CodexIngestStats:
    """Outcome of ingesting rollout files (skips/duplicates reported, never silent)."""

    files: int
    records: int
    skipped: int
    duplicates: int
    dangling: int


def ingest_rollouts(
    paths: list[Path], store: RecordStore, *, redaction: RedactionConfig | None = None
) -> CodexIngestStats:
    """Read rollout files into ``store``; idempotent on ``(session_id, span_id)``."""
    files = records = skipped = duplicates = dangling = 0
    existing = {
        (record.session_id, record.span_id, record.step_type) for record in store.records()
    }
    for path in paths:
        files += 1
        try:
            read = read_rollout(path, redaction=redaction)
        except (OSError, CodexRolloutError):
            skipped += 1
            continue
        skipped += read.skipped
        duplicates += read.duplicates
        if read.dangling:
            dangling += 1
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
                records += 1
                existing.add(key)
    return CodexIngestStats(
        files=files,
        records=records,
        skipped=skipped,
        duplicates=duplicates,
        dangling=dangling,
    )


__all__ = [
    "CODEX_PRODUCER",
    "DANGLING_AFTER_MINUTES",
    "CodexIngestStats",
    "CodexRolloutError",
    "RolloutRead",
    "ingest_rollouts",
    "read_rollout",
]
