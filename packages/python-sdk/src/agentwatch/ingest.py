"""OTel GenAI / NDJSON ingestion (M10 N2 #213).

Transcode foreign traces into the local store — the same motion as transcript
import (H1), generalized. Foreign content is **untrusted**: it is mapped strictly
(reject-never-invent), secrets are masked before storage (DD-06), and records that
do not validate or spans that cannot be mapped are quarantined with a reason
(B4/F8), never dropped silently. Ingest is local file/stdin; no egress (R6).

Scope is deliberately narrow (D-Q): agentwatch is **not** a general OTel backend —
only GenAI spans/attributes that map onto records + security events land here.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, cast

from agentwatch.aat import AAT_DRAFT, aat_entry_chain_error
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

HARNESS_ID = "otel"

# Foreign OTel/NDJSON traces are ingested, not live-captured (M15 S26).
INGEST_PRODUCER = Producer(kind=ProducerKind.INGEST, name=HARNESS_ID)

_PRIVACY_MAP = {
    PrivacyMode.METADATA_ONLY: RecordPrivacyMode.METADATA_ONLY,
    PrivacyMode.TRUNCATED: RecordPrivacyMode.TRUNCATED,
    PrivacyMode.HASHED: RecordPrivacyMode.HASHED,
    PrivacyMode.FULL: RecordPrivacyMode.FULL,
}

_ERROR_STATUS = frozenset({2, "2", "STATUS_CODE_ERROR", "ERROR", "error"})


class IngestError(ValueError):
    """Raised when a foreign trace element cannot be transcoded."""


@dataclass(frozen=True)
class IngestProblem:
    """One element that failed to transcode (quarantined, never dropped)."""

    source: str
    reason: str


@dataclass(frozen=True)
class IngestStats:
    """Outcome of one ingest run (skips/duplicates/problems are reported)."""

    files: int
    records: int
    skipped: int
    duplicates: int
    problems: tuple[IngestProblem, ...] = ()


# ---------------------------------------------------------------------------
# OTLP decoding helpers
# ---------------------------------------------------------------------------


def _any_value(value: Any) -> Any:
    """Decode one OTLP ``AnyValue`` (or pass a plain value through)."""
    if not isinstance(value, Mapping):
        return value
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        try:
            return int(value["intValue"])
        except (TypeError, ValueError):
            return value["intValue"]
    if "doubleValue" in value:
        try:
            return float(value["doubleValue"])
        except (TypeError, ValueError):
            return value["doubleValue"]
    if "bytesValue" in value:
        return value["bytesValue"]
    if "arrayValue" in value:
        array = value["arrayValue"]
        values = array.get("values") if isinstance(array, Mapping) else None
        return [_any_value(item) for item in values] if isinstance(values, list) else []
    if "kvlistValue" in value:
        kvlist = value["kvlistValue"]
        values = kvlist.get("values") if isinstance(kvlist, Mapping) else None
        if not isinstance(values, list):
            return {}
        return {
            item["key"]: _any_value(item.get("value"))
            for item in values
            if isinstance(item, Mapping) and isinstance(item.get("key"), str)
        }
    return value


def _attributes(raw: Any) -> dict[str, Any]:
    """Accept OTLP attribute lists or a plain mapping."""
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, list):
        result: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, Mapping) and isinstance(item.get("key"), str):
                result[item["key"]] = _any_value(item.get("value"))
        return result
    return {}


def _flatten_spans(payload: Any) -> list[Mapping[str, Any]]:
    """Find OTel spans in an OTLP resource/scope envelope, a list, or a lone span."""
    if isinstance(payload, list):
        spans: list[Mapping[str, Any]] = []
        for item in payload:
            spans.extend(_flatten_spans(item))
        return spans
    if not isinstance(payload, Mapping):
        return []
    direct = payload.get("spans")
    if isinstance(direct, list):
        return [span for span in direct if isinstance(span, Mapping)]
    resource = payload.get("resourceSpans")
    if isinstance(resource, list):
        spans = []
        for resource_span in resource:
            if not isinstance(resource_span, Mapping):
                continue
            scopes = resource_span.get("scopeSpans") or resource_span.get(
                "instrumentationLibrarySpans"
            )
            if not isinstance(scopes, list):
                continue
            for scope in scopes:
                if isinstance(scope, Mapping) and isinstance(scope.get("spans"), list):
                    spans.extend(s for s in scope["spans"] if isinstance(s, Mapping))
        return spans
    if any(key in payload for key in ("name", "traceId", "spanId", "startTimeUnixNano")):
        return [payload]
    return []


def _nanos(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        nanos = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(nanos / 1e9, tz=timezone.utc)


def _redact(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, Mapping):
        return {key: _redact(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, cfg) for item in value]
    return value


def _capture(
    attrs: Mapping[str, Any], cfg: RedactionConfig | None
) -> tuple[dict[str, Any] | None, RecordPrivacyMode]:
    if cfg is None or cfg.mode is PrivacyMode.METADATA_ONLY or not cfg.capture_tool_args:
        return None, RecordPrivacyMode.METADATA_ONLY
    masked, _ = redact_mapping(attrs)
    return cast("dict[str, Any]", _redact(masked, cfg)), _PRIVACY_MAP[cfg.mode]


# ---------------------------------------------------------------------------
# Transcoding
# ---------------------------------------------------------------------------

# Gateway-reported exact cost attributes (source-stamped, GWY-2).
_COST_KEYS = (
    "gen_ai.usage.cost",
    "gen_ai.usage.total_cost",
    "portkey.cost",
    "litellm.cost",
    "llm.cost",
)


def _usage_tokens(attrs: Mapping[str, Any]) -> int | None:
    total = attrs.get("gen_ai.usage.total_tokens")
    if total is not None:
        try:
            return int(total)
        except (TypeError, ValueError):
            pass
    prompt = attrs.get("gen_ai.usage.prompt_tokens", attrs.get("gen_ai.usage.input_tokens"))
    completion = attrs.get(
        "gen_ai.usage.completion_tokens", attrs.get("gen_ai.usage.output_tokens")
    )
    if prompt is None and completion is None:
        return None
    try:
        return int(prompt or 0) + int(completion or 0)
    except (TypeError, ValueError):
        return None


def _usage_cost(attrs: Mapping[str, Any]) -> float | None:
    for key in _COST_KEYS:
        value = attrs.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None



def _span_to_record(
    span: Mapping[str, Any],
    *,
    source: str,
    redaction: RedactionConfig | None,
) -> AgentRecord:
    attrs = _attributes(span.get("attributes"))
    operation = attrs.get("gen_ai.operation.name")
    tool_name = attrs.get("gen_ai.tool.name") or operation
    if not isinstance(tool_name, str) or not tool_name:
        tool_name = span.get("name") if isinstance(span.get("name"), str) else None

    start = _nanos(span.get("startTimeUnixNano")) or datetime.now(timezone.utc)
    end = _nanos(span.get("endTimeUnixNano"))
    if tool_name is None and end is None:
        raise IngestError("span has no tool/operation name and no end time")

    status = span.get("status")
    code = status.get("code") if isinstance(status, Mapping) else None
    outcome = Outcome.ERROR if code in _ERROR_STATUS else Outcome.OK

    conversation = attrs.get("gen_ai.conversation.id")
    session_id = str(conversation) if conversation else str(span.get("traceId") or source)
    raw_span_id = span.get("spanId") or span.get("span_id")
    # Namespace by source so two foreign traces with the same span id cannot collide.
    span_id = f"{source}:{raw_span_id}" if raw_span_id else None
    trace_id = str(span.get("traceId") or session_id)

    _, kinds = redact_mapping(span)
    security_event = (
        SecurityEvent(
            type=SecurityEventType.SECRET_DETECTED,
            emitted_at=end or start,
            emitter="agentwatch",
            tool=tool_name,
            evidence={"kinds": list(kinds)},
        )
        if kinds
        else None
    )
    captured, privacy_mode = _capture(attrs, redaction)
    tool_kwargs: dict[str, Any] = {"name": tool_name or operation or "span"}
    if captured is not None:
        tool_kwargs["arguments"] = captured
        tool_kwargs["privacy_mode"] = privacy_mode

    duration = (end - start).total_seconds() * 1000 if end is not None else None
    record = AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity=str(attrs.get("gen_ai.agent.name") or HARNESS_ID)),
        tool=ToolCall(**tool_kwargs),
        outcome=outcome,
        started_at=start,
        trace_id=trace_id,
        span_id=span_id,
        harness=HARNESS_ID,
        producer=INGEST_PRODUCER,
        project=str(attrs["cwd"]) if isinstance(attrs.get("cwd"), str) else None,
        ended_at=end,
        duration_ms=duration,
        step_type=StepType.OBSERVE if end is not None else StepType.ACT,
        security_event=security_event,
        tokens=_usage_tokens(attrs),
        cost_usd=_usage_cost(attrs),
    )
    validate_record(record.to_dict())
    return record


def transcode_otel(
    payload: Any,
    *,
    source: str = "otel",
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode one OTLP payload into records + problems (never raises per span)."""
    spans = _flatten_spans(payload)
    if not spans:
        return [], [IngestProblem(source, "no OTel spans found")]
    records: list[AgentRecord] = []
    problems: list[IngestProblem] = []
    for index, span in enumerate(spans):
        try:
            records.append(_span_to_record(span, source=source, redaction=redaction))
        except (IngestError, ValueError, KeyError, TypeError) as exc:
            problems.append(IngestProblem(f"{source}#{index}", f"unmappable span: {exc}"))
    return records, problems


def transcode_ndjson(
    text: str,
    *,
    source: str = "ndjson",
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode newline-delimited JSON (one OTLP payload or span per line)."""
    records: list[AgentRecord] = []
    problems: list[IngestProblem] = []
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(IngestProblem(f"{source}#{index}", f"invalid JSON: {exc}"))
            continue
        found, probs = transcode_otel(payload, source=f"{source}#{index}", redaction=redaction)
        records.extend(found)
        problems.extend(probs)
    return records, problems


def transcode_aat(
    text: str,
    *,
    source: str = "aat",
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode a foreign IETF AAT bundle (M26 AAT-3).

    The bundle is untrusted: every entry's chain hash and inter-entry linkage is
    verified before its record is stored (fail closed), and any record that does
    not pass chain verification or cannot be normalized is quarantined with a
    reason (B4) rather than dropped or trusted. Foreign content is always run
    through the secrets pipeline before storage.
    """
    try:
        bundle = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], [IngestProblem(source, f"invalid JSON: {exc}")]
    if not isinstance(bundle, Mapping):
        return [], [IngestProblem(source, "AAT bundle is not a JSON object")]
    revision = bundle.get("aat_version")
    if revision != AAT_DRAFT:
        return [], [IngestProblem(source, f"unsupported AAT revision: {revision!r}")]
    entries = bundle.get("records")
    if not isinstance(entries, list):
        return [], [IngestProblem(source, "AAT bundle has no records list")]

    records: list[AgentRecord] = []
    problems: list[IngestProblem] = []
    prev_hash: str | None = None
    for index, entry in enumerate(entries):
        here = f"{source}#{index}"
        error = aat_entry_chain_error(entry, prev_hash)
        chain = entry.get("chain") if isinstance(entry, Mapping) else None
        declared = chain.get("hash") if isinstance(chain, Mapping) else None
        if error is not None:
            problems.append(IngestProblem(here, f"untrusted AAT record: {error}"))
        else:
            native, _ = redact_mapping(entry["agentwatch"])
            try:
                record = AgentRecord.from_dict(native)
                validate_record(record.to_dict())
            except (ValueError, KeyError, TypeError) as exc:
                problems.append(IngestProblem(here, f"non-normalizable AAT record: {exc}"))
            else:
                records.append(record)
        # Track the entry's declared link even when it fails, so one bad entry
        # does not cascade into false linkage errors for its successors.
        if isinstance(declared, str):
            prev_hash = declared
    return records, problems


# ---------------------------------------------------------------------------
# OTLP protobuf / gRPC (M26 OTEL-3)
# ---------------------------------------------------------------------------

# OTLP JSON renders trace/span ids as hex; protobuf's JSON mapping base64-encodes
# bytes, so these keys are normalized back to hex for the shared transcode path.
_OTLP_ID_KEYS = frozenset({"traceId", "spanId", "parentSpanId"})
_GRPC_HEADER_BYTES = 5


def _b64_hex(value: str) -> str:
    if not value:
        return value
    try:
        return base64.b64decode(value).hex()
    except (binascii.Error, ValueError):
        return value


def _ids_to_hex(node: Any) -> Any:
    if isinstance(node, Mapping):
        return {
            key: _b64_hex(value)
            if key in _OTLP_ID_KEYS and isinstance(value, str)
            else _ids_to_hex(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_ids_to_hex(item) for item in node]
    return node


def _decode_otlp_protobuf(data: bytes) -> Mapping[str, Any]:
    """Decode a bare ``ExportTraceServiceRequest`` into the OTLP JSON shape."""
    try:
        from google.protobuf.json_format import MessageToDict
        from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
    except ImportError as exc:  # pragma: no cover - optional [otlp] extra
        raise IngestError(
            "OTLP protobuf ingest requires the [otlp] extra "
            "(pip install 'agentsec-agentwatch[otlp]')"
        ) from exc
    request = trace_service_pb2.ExportTraceServiceRequest()
    request.ParseFromString(data)
    payload = MessageToDict(request)
    return cast("Mapping[str, Any]", _ids_to_hex(payload))


def transcode_otlp_protobuf(
    data: bytes,
    *,
    source: str = "otlp",
    redaction: RedactionConfig | None = None,
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Transcode one bare OTLP protobuf request; undecodable bytes are a problem."""
    try:
        payload = _decode_otlp_protobuf(data)
    except IngestError as exc:
        return [], [IngestProblem(source, str(exc))]
    except Exception as exc:  # protobuf DecodeError and friends, never raised on
        return [], [IngestProblem(source, f"undecodable OTLP protobuf: {exc}")]
    return transcode_otel(payload, source=source, redaction=redaction)


def iter_grpc_messages(stream: BinaryIO) -> Iterator[bytes]:
    """Yield the protobuf payload of each gRPC length-prefixed frame.

    Reads one frame at a time (header + bounded body) so a large stream is never
    fully loaded. Compressed frames are rejected rather than mis-decoded.
    """
    while True:
        header = stream.read(_GRPC_HEADER_BYTES)
        if not header:
            return
        if len(header) < _GRPC_HEADER_BYTES:
            raise IngestError("truncated gRPC frame header")
        if header[0] != 0:
            raise IngestError("compressed gRPC frames are not supported")
        length = int.from_bytes(header[1:], "big")
        body = stream.read(length)
        if len(body) != length:
            raise IngestError("truncated gRPC frame body")
        yield body


def transcode_grpc_chunks(
    stream: BinaryIO,
    *,
    source: str = "otlp-grpc",
    redaction: RedactionConfig | None = None,
) -> Iterator[tuple[list[AgentRecord], list[IngestProblem], bytes]]:
    """Stream a gRPC-framed OTLP file as ``(records, problems, raw)`` chunks."""
    try:
        messages = iter_grpc_messages(stream)
        for index, body in enumerate(messages):
            found, probs = transcode_otlp_protobuf(
                body, source=f"{source}#{index}", redaction=redaction
            )
            yield found, probs, body
    except IngestError as exc:
        yield [], [IngestProblem(source, str(exc))], b""


# ---------------------------------------------------------------------------
# Store ingestion
# ---------------------------------------------------------------------------

def resolve_ingest_paths(target: Path) -> list[Path]:
    """Resolve a source file or a directory of ``*.json`` / ``*.jsonl`` files."""
    if target.is_dir():
        return sorted(
            [
                *target.rglob("*.json"),
                *target.rglob("*.jsonl"),
                *target.rglob("*.jsonl.zst"),
                *target.rglob("*.pb"),
                *target.rglob("*.otlp"),
            ]
        )
    return [target]


def transcode(
    path: Path, *, fmt: str, source: str | None = None, redaction: RedactionConfig | None = None
) -> tuple[list[AgentRecord], list[IngestProblem]]:
    """Read one source file and transcode it by ``fmt``.

    ``otel`` accepts JSON and, auto-detected, a bare OTLP protobuf
    ``ExportTraceServiceRequest``; the JSON path is unchanged.
    """
    name = source or path.stem
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [], [IngestProblem(name, f"unreadable: {exc}")]
    text = raw.decode("utf-8", errors="replace")
    if fmt == "ndjson":
        return transcode_ndjson(text, source=name, redaction=redaction)
    if fmt == "aat":
        return transcode_aat(text, source=name, redaction=redaction)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return transcode_otlp_protobuf(raw, source=name, redaction=redaction)
    return transcode_otel(payload, source=name, redaction=redaction)


def run_ingest(
    paths: Iterable[Path],
    store: RecordStore,
    *,
    fmt: str = "otel",
    quarantine: QuarantineLog | None = None,
    redaction: RedactionConfig | None = None,
    source: str | None = None,
) -> IngestStats:
    """Transcode foreign traces into ``store``; report counts + problems.

    Idempotent on ``(session_id, span_id)`` so re-ingesting the same trace does not
    inflate the store. Unmappable input is quarantined (when a log is given) and
    counted, never dropped silently. ``otlp-grpc`` streams frame by frame so a
    large file is never fully loaded.
    """
    files = 0
    records = 0
    skipped = 0
    duplicates = 0
    problems: list[IngestProblem] = []
    existing = {(record.session_id, record.span_id) for record in store.records()}

    def _add(
        found: Iterable[AgentRecord], probs: Iterable[IngestProblem], raw: bytes | str
    ) -> None:
        nonlocal records, skipped, duplicates
        probs = list(probs)
        problems.extend(probs)
        if quarantine is not None:
            for problem in probs:
                quarantine.add(raw, reason=problem.reason)
        for record in found:
            key = (record.session_id, record.span_id)
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

    for path in paths:
        files += 1
        name = source or path.stem
        if fmt == "otlp-grpc":
            with path.open("rb") as handle:
                for found, probs, raw in transcode_grpc_chunks(
                    handle, source=name, redaction=redaction
                ):
                    _add(found, probs, raw)
            continue
        found, probs = transcode(path, fmt=fmt, source=name, redaction=redaction)
        _add(found, probs, path.read_bytes().decode("utf-8", errors="replace"))
    return IngestStats(
        files=files,
        records=records,
        skipped=skipped,
        duplicates=duplicates,
        problems=tuple(problems),
    )
