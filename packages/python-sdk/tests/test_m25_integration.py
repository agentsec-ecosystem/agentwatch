"""M25 Foundations integration tests (25.T, #371).

Where the per-ticket unit tests prove one component, these compose the M25 pieces
end to end along the real paths: Cursor hooks -> store -> replay, Gemini
telemetry file -> ingest -> store, AAT export -> verify, the streaming transport
against store truth, and the privacy modes on the ingest/export boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentwatch.aat import export_aat, verify_aat
from agentwatch.adapters import cursor
from agentwatch.ingest import run_ingest
from agentwatch.records import validate_record
from agentwatch.redact import PrivacyMode, RedactionConfig, redaction_config_from_mode
from agentwatch.replay import replay_session
from agentwatch.sampling import SampleDecision, SecurityRelevantSampler
from agentwatch.session_export import export_session
from agentwatch.store import RecordStore
from agentwatch.streaming import StreamHub

AT = "2026-01-02T03:04:05+00:00"
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def _cursor(phase: str, **event: Any) -> dict[str, Any]:
    body = {"session_id": "sess-1", "timestamp": AT, **event}
    return {"phase": phase, "harness": "cursor", "event": body}


def test_cursor_hook_stream_replays_through_the_store(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    frames = [
        _cursor("sessionStart", ide="cursor-cli"),
        _cursor("beforeShellExecution", call_id="c1", command="npm test"),
        _cursor("afterShellExecution", call_id="c1", started_at=AT),
        _cursor("beforeReadFile", call_id="c2", file="a.py"),
        _cursor("beforeSubmitPrompt", prompt="go"),
        _cursor("sessionEnd", reason="exit"),
    ]

    for frame in frames:
        for record in cursor.normalize(frame):
            store.append(record)

    assert store.verify().ok
    ordered = replay_session(store, "sess-1")
    assert [record.tool.name for record in ordered] == [
        "session-start",
        "Shell",
        "Shell",
        "Read",
        "user-prompt",
        "session-end",
    ]
    for record in ordered:
        validate_record(record.to_dict())


def test_cursor_oversized_segment_is_contained_and_truncated() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True, truncate_at=64)
    (record,) = cursor.normalize(
        _cursor("preToolUse", call_id="c", tool_name="Bash", tool_input={"command": "x" * 10_000}),
        redaction=cfg,
    )

    validate_record(record.to_dict())
    assert record.tool.arguments is not None
    captured = record.tool.arguments["command"]
    assert len(captured) <= 64


def _gemini_payload() -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "gemini-cli"}},
                        {"key": "session.id", "value": {"stringValue": "gem-sess-1"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "gsp-1",
                                "traceId": "gtrace-1",
                                "name": "execute_tool",
                                "startTimeUnixNano": "1767000000000000000",
                                "endTimeUnixNano": "1767000000050000000",
                                "attributes": [
                                    {
                                        "key": "gen_ai.tool.name",
                                        "value": {"stringValue": "run_shell"},
                                    },
                                    {
                                        "key": "gen_ai.tool.args",
                                        "value": {"stringValue": "export TOKEN=sk-abcdefgh1234"},
                                    },
                                ],
                            }
                        ]
                    }
                ],
            }
        ]
    }


def test_gemini_telemetry_file_ingests_redacted_into_store(tmp_path: Path) -> None:
    telemetry = tmp_path / "gemini-telemetry.json"
    telemetry.write_text(json.dumps(_gemini_payload()), encoding="utf-8")
    store = RecordStore(tmp_path / "records.jsonl")

    stats = run_ingest(
        [telemetry],
        store,
        fmt="otel",
        source="gemini",
        redaction=redaction_config_from_mode("full"),
    )

    assert stats.records == 1
    assert not stats.problems
    assert store.verify().ok
    dumped = json.dumps([record.to_dict() for record in store.records()])
    assert "sk-abcdefgh1234" not in dumped


@pytest.mark.parametrize("mode", ["metadata-only", "truncated", "hashed", "full"])
def test_privacy_modes_never_leak_content_on_the_ingest_boundary(
    tmp_path: Path, mode: str
) -> None:
    telemetry = tmp_path / f"gemini-{mode}.json"
    telemetry.write_text(json.dumps(_gemini_payload()), encoding="utf-8")
    store = RecordStore(tmp_path / f"records-{mode}.jsonl")

    run_ingest(
        [telemetry],
        store,
        fmt="otel",
        source="gemini",
        redaction=redaction_config_from_mode(mode),
    )

    dumped = json.dumps([record.to_dict() for record in store.records()])
    assert "sk-abcdefgh1234" not in dumped
    for record in store.records():
        validate_record(record.to_dict())


def test_aat_export_round_trips_trace_identity_and_chain(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    events = [
        _cursor(
            "beforeShellExecution",
            call_id="c1",
            command="ls",
            traceparent=TRACEPARENT,
            agent={"principal": "alice", "credential_class": "oauth"},
        ),
        _cursor("afterShellExecution", call_id="c1", started_at=AT, traceparent=TRACEPARENT),
    ]
    for message in events:
        for record in cursor.normalize(message):
            store.append(record)

    export = export_session(store, "sess-1")
    bundle = export_aat(export, privacy_mode="metadata-only")

    assert verify_aat(bundle) is True
    entry = bundle["records"][0]
    native = entry["agentwatch"]
    assert native["traceparent"] == TRACEPARENT
    assert native["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    # The principal is hashed by default (IDN-1) and never stored in the clear.
    assert entry["agent"]["principal"] != "alice"
    assert entry["unmapped"]  # lossless-or-explicit: gaps are named, not silent


def test_streaming_drop_consumer_preserves_store_truth(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    hub: StreamHub[str] = StreamHub(queue_size=1)
    subscriber = hub.subscribe()

    # Append first (store truth), then stream a derived view.
    (record,) = cursor.normalize(_cursor("beforeShellExecution", call_id="c1", command="ls"))
    store.append(record)
    assert hub.publish("event-1") is True
    assert hub.publish("event-2") is False  # bounded queue overflows, visible
    assert hub.degraded is True
    assert store.verify().ok  # a dropped consumer never loses a stored record

    hub.unsubscribe(subscriber)
    assert hub.degraded is False


def test_sampler_decisions_are_stable_across_replay_and_keep_evidence(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    frames = [
        _cursor("beforeShellExecution", call_id="c1", command="ls"),
        _cursor("beforeSubmitPrompt", prompt="go"),
    ]
    for frame in frames:
        for record in cursor.normalize(frame):
            store.append(record)

    sampler = SecurityRelevantSampler()
    records = store.records()
    first = [sampler.should_sample(record, ratio=0.0) for record in records]
    second = [sampler.should_sample(record, ratio=0.0) for record in records]

    assert first == second  # deterministic across a replay
    assert all(decision is SampleDecision.SAMPLED_OUT for decision in first)


def test_secret_bearing_record_is_always_kept() -> None:
    (record,) = cursor.normalize(
        _cursor("beforeShellExecution", call_id="c1", command="export TOKEN=sk-abcdefgh")
    )
    assert record.security_event is not None
    assert SecurityRelevantSampler().should_sample(record, ratio=0.0) is SampleDecision.ALWAYS
