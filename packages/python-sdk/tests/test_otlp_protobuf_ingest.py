"""OTLP protobuf / gRPC ingest tests (M26 OTEL-3, #316).

The JSON path must stay unchanged; a bare protobuf ``ExportTraceServiceRequest``
is accepted under ``--format otel`` (auto-detected), and a gRPC length-prefixed
stream is decoded incrementally so a large file is never fully loaded.
"""

from __future__ import annotations

import io
import json
import tracemalloc
from pathlib import Path

import pytest

from agentwatch.ingest import (
    IngestError,
    iter_grpc_messages,
    transcode,
    transcode_grpc_chunks,
    transcode_otlp_protobuf,
    run_ingest,
)
from agentwatch.records import validate_record
from agentwatch.store import RecordStore

pytest.importorskip("opentelemetry.proto")

from opentelemetry.proto.collector.trace.v1 import trace_service_pb2  # noqa: E402
from opentelemetry.proto.common.v1 import common_pb2  # noqa: E402
from opentelemetry.proto.trace.v1 import trace_pb2  # noqa: E402

HEX_TRACE = "11" * 16
HEX_SPAN = "22" * 8


def _kv(key: str, value: str) -> common_pb2.KeyValue:
    return common_pb2.KeyValue(key=key, value=common_pb2.AnyValue(string_value=value))


def _span(name: str = "get_weather") -> trace_pb2.Span:
    return trace_pb2.Span(
        trace_id=bytes.fromhex(HEX_TRACE),
        span_id=bytes.fromhex(HEX_SPAN),
        name=name,
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_001_000_000_000,
        attributes=[
            _kv("gen_ai.tool.name", name),
            _kv("gen_ai.agent.name", "weather-bot"),
            _kv("gen_ai.conversation.id", "conv-1"),
        ],
    )


def _request(spans: list[trace_pb2.Span]) -> trace_service_pb2.ExportTraceServiceRequest:
    return trace_service_pb2.ExportTraceServiceRequest(
        resource_spans=[
            trace_pb2.ResourceSpans(scope_spans=[trace_pb2.ScopeSpans(spans=spans)])
        ]
    )


def _grpc_frames(messages: list[bytes]) -> bytes:
    out = bytearray()
    for message in messages:
        out.append(0)  # uncompressed
        out += len(message).to_bytes(4, "big")
        out += message
    return bytes(out)


def test_transcode_bare_protobuf_message() -> None:
    data = _request([_span()]).SerializeToString()

    records, problems = transcode_otlp_protobuf(data)

    assert problems == []
    assert len(records) == 1
    validate_record(records[0].to_dict())
    assert records[0].tool.name == "get_weather"
    assert records[0].agent.identity == "weather-bot"
    assert records[0].session_id == "conv-1"
    assert records[0].trace_id == HEX_TRACE
    assert records[0].span_id == f"otlp:{HEX_SPAN}"


def test_transcode_auto_detects_protobuf_under_otel(tmp_path: Path) -> None:
    path = tmp_path / "trace.pb"
    path.write_bytes(_request([_span("search")]).SerializeToString())

    records, problems = transcode(path, fmt="otel")

    assert problems == []
    assert [record.tool.name for record in records] == ["search"]


def test_json_path_is_unchanged(tmp_path: Path) -> None:
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "trace-1",
                                "spanId": "sp-1",
                                "name": "get_weather",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000001000000000",
                                "attributes": [
                                    {"key": "gen_ai.conversation.id", "value": {"stringValue": "c"}}
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    records, problems = transcode(path, fmt="otel")

    assert problems == []
    assert records[0].tool.name == "get_weather"


def test_grpc_stream_is_decoded_without_loading_the_whole_stream() -> None:
    frames = _grpc_frames([_request([_span(f"tool-{i}")]).SerializeToString() for i in range(25)])

    class _NoFullRead(io.BytesIO):
        def read(self, size: int | None = -1, /) -> bytes:
            assert size is not None and size >= 0, "reader must not load the whole stream"
            return super().read(size)

    messages = list(iter_grpc_messages(_NoFullRead(frames)))

    assert len(messages) == 25


def test_grpc_stream_rejects_a_compressed_frame() -> None:
    message = _request([_span()]).SerializeToString()
    framed = b"\x01" + len(message).to_bytes(4, "big") + message

    with pytest.raises(IngestError, match="compressed"):
        list(iter_grpc_messages(io.BytesIO(framed)))


def test_run_ingest_streams_a_grpc_file(tmp_path: Path) -> None:
    messages = [_request([_span(f"tool-{i}")]).SerializeToString() for i in range(30)]
    path = tmp_path / "stream.otlp"
    path.write_bytes(_grpc_frames(messages))
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest([path], store, fmt="otlp-grpc")

    assert stats.records == 30
    assert stats.problems == ()
    assert store.verify().ok


def test_large_grpc_stream_has_bounded_memory(tmp_path: Path) -> None:
    message = _request([_span()]).SerializeToString()
    frame = b"\x00" + len(message).to_bytes(4, "big") + message
    path = tmp_path / "big.otlp"
    with path.open("wb") as handle:
        for _ in range(20000):
            handle.write(frame)
    assert path.stat().st_size > 3_000_000

    tracemalloc.start()
    count = 0
    with path.open("rb") as handle:
        for found, _problems, _raw in transcode_grpc_chunks(handle):
            count += len(found)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Decoding reads one frame at a time, so the peak is independent of file size.
    assert count == 20000
    assert peak < 2_000_000


def test_cli_ingest_protobuf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    path = tmp_path / "trace.pb"
    path.write_bytes(_request([_span()]).SerializeToString())

    from agentwatch.cli.main import main

    rc = main(["ingest", str(path), "--format", "otel", "--json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["records"] == 1
