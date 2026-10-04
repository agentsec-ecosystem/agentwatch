"""OTel Collector component mapping (M20 S39, PRD 36).

R4 claims records load into standard backends unmodified; the honest answer is
"after you configure a collector correctly." This is the last mile: a thin
receiver mapping that reads the agentwatch store and emits GenAI-semconv spans,
so a collector config can point at it directly.

The **mapping lives in agentwatch** and the collector component stays thin (PRD
36 S39 risk mitigation): this module is pure — no network, no dependency on the
collector API. A missing store reports ``unavailable`` and fabricates nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.export import record_to_attributes, security_event_attributes
from agentwatch.records import AgentRecord
from agentwatch.semconv import SEMCONV_VERSION
from agentwatch.store import RecordStore

COMPONENT_NAME = "agentwatchreceiver"
COMPONENT_VERSION = "0.1.0"
SERVICE_NAME = "agentwatch"


def _hex_id(value: str, *, nbytes: int) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[: nbytes * 2]


@dataclass(frozen=True)
class SpanRecord:
    """One GenAI-semconv span derived from a record."""

    trace_id: str
    span_id: str
    name: str
    attributes: dict[str, Any]
    start_time_unix_nano: int
    events: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time_unix_nano": self.start_time_unix_nano,
            "attributes": self.attributes,
            "events": list(self.events),
        }


def record_to_span(record: AgentRecord, seq: int) -> SpanRecord:
    """Map one record to a semconv span record (pure)."""
    logical_trace = record.trace_id or record.session_id
    events: list[dict[str, Any]] = []
    if record.security_event is not None:
        events.append(
            {
                "name": record.security_event.type.value,
                "attributes": security_event_attributes(record.security_event),
            }
        )
    return SpanRecord(
        trace_id=_hex_id(logical_trace, nbytes=16),
        span_id=_hex_id(f"{logical_trace}:{seq}", nbytes=8),
        name=record.tool.name,
        attributes=record_to_attributes(record, seq),
        start_time_unix_nano=int(record.started_at.timestamp() * 1_000_000_000),
        events=tuple(events),
    )


def collect_spans(store: RecordStore) -> list[SpanRecord]:
    """Every record as a semconv span, in store order."""
    spans: list[SpanRecord] = []
    for entry in store.entries():
        if entry.record is not None:
            spans.append(record_to_span(entry.record, entry.seq))
    return spans


def resource_attributes() -> dict[str, Any]:
    """The receiver's resource attributes, carrying the pinned semconv version."""
    return {
        "service.name": SERVICE_NAME,
        "telemetry.sdk.name": "agentwatch",
        "otel.semconv.version": SEMCONV_VERSION,
    }


def receiver_status(store_path: Path | str) -> str:
    """``ok`` when the store exists and has records, else ``unavailable``.

    Unavailable is stated plainly — the receiver never fabricates spans.
    """
    path = Path(store_path)
    if not path.exists():
        return "unavailable"
    if not RecordStore(path).records():
        return "unavailable"
    return "ok"


def component_manifest() -> dict[str, Any]:
    """A minimal manifest for the collector-component packaging path."""
    return {
        "name": COMPONENT_NAME,
        "version": COMPONENT_VERSION,
        "kind": "receiver",
        "emits": "traces",
        "semconv_version": SEMCONV_VERSION,
    }


__all__ = [
    "COMPONENT_NAME",
    "COMPONENT_VERSION",
    "SEMCONV_VERSION",
    "SERVICE_NAME",
    "SpanRecord",
    "collect_spans",
    "component_manifest",
    "record_to_span",
    "receiver_status",
    "resource_attributes",
]
