"""Register the LangGraph SDK conformance pack (M27 LG-1, O1).

An SDK pack replays instrumentation input (LangGraph callback events) through the
real ``_NodeCallbackHandler``, exports the resulting OTel spans, and transcodes
them to records with the shared OTel path — the same route the SDK uses. The
pack holds the instrumentation→record mapping to the O1 bar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentwatch import conformance
from agentwatch.config import SDKConfig
from agentwatch.ingest import transcode_otel
from agentwatch.langgraph import _NodeCallbackHandler
from agentwatch.records import AgentRecord
from agentwatch.tracer import configure_tracing, reset_tracing

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "langgraph-sdk"


def _span_payload(span: Any) -> dict[str, Any]:
    """A span → the OTLP-ish mapping the shared OTel transcoder accepts."""
    return {
        "name": span.name,
        "traceId": format(span.context.trace_id, "032x"),
        "spanId": format(span.context.span_id, "016x"),
        "startTimeUnixNano": str(span.start_time),
        "endTimeUnixNano": str(span.end_time) if span.end_time else None,
        "attributes": dict(span.attributes or {}),
        "status": {"code": span.status.status_code.value},
    }


def replay_langgraph(events: Any) -> list[AgentRecord]:
    """Drive the LangGraph handler with callback events and transcode to records."""
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    try:
        handler = _NodeCallbackHandler()
        for event in events:
            kind = event.get("type")
            run_id = str(event.get("run_id", ""))
            if kind == "chain_start":
                handler.on_chain_start(
                    serialized={},
                    inputs=event.get("inputs", {}),
                    run_id=run_id,
                    tags=event.get("tags", []),
                    metadata=event.get("metadata", {}),
                )
            elif kind == "chain_end":
                handler.on_chain_end(outputs=event.get("outputs", {}), run_id=run_id)
            elif kind == "chain_error":
                handler.on_chain_error(Exception(str(event.get("error", "error"))), run_id=run_id)
        payload = [_span_payload(span) for span in exporter.get_finished_spans()]
        records, _problems = transcode_otel(payload, source="langgraph")
        return records
    finally:
        reset_tracing()


def langgraph_spec() -> conformance.SdkSpec:
    return conformance.SdkSpec(
        name="langgraph",
        replay=replay_langgraph,
        fixtures_dir=FIXTURES,
        error_cls=ValueError,
    )


def register_sdk_packs() -> None:
    if "langgraph" not in {spec.name for spec in conformance.registered_sdks()}:
        conformance.register_sdk(langgraph_spec())


register_sdk_packs()

__all__ = ["FIXTURES", "langgraph_spec", "register_sdk_packs", "replay_langgraph"]
