"""System-effects ingest: AgentSight/Tracee-shaped events, opt-in (M29 SYS-1, #366).

The lower layer is foreign and never silently trusted: it is opt-in, every record
is labeled ``source: system-ingest``, a record whose process lineage is not owned
by a session is *not* attributed to one, and the lineage join's false-join
precision is published from a committed synthetic corpus.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from agentwatch import system_ingest
from agentwatch.classify import NETWORK, classify_record
from agentwatch.impact import build_impact
from agentwatch.records import ProducerKind, RecordPrivacyMode, SecurityEventType, validate_record
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "system-ingest"


def _agentsight(*events: dict[str, Any]) -> list[dict[str, Any]]:
    return list(events)


def _tracee(*events: dict[str, Any]) -> dict[str, Any]:
    return {"events": list(events)}


# --- opt-in gate -------------------------------------------------------------


def test_ingest_requires_explicit_optin() -> None:
    with pytest.raises(system_ingest.SystemIngestNotOptedInError):
        system_ingest.transcode_system_ingest(_agentsight(), opted_in=False)


def test_linux_is_covered_and_darwin_windows_are_not() -> None:
    assert system_ingest.platform_covered("linux")
    assert not system_ingest.platform_covered("darwin")
    assert not system_ingest.platform_covered("windows")


# --- shape mapping -----------------------------------------------------------


def test_agentsight_process_and_network_events_map() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "process_exec",
                "pid": 100,
                "ppid": 1,
                "comm": "node",
                "timestamp": "2026-01-02T03:04:05Z",
                "session_id": "s1",
            },
            {
                "type": "network_connect",
                "pid": 102,
                "ppid": 100,
                "comm": "node",
                "daddr": "93.184.216.34",
                "dport": 443,
                "timestamp": "2026-01-02T03:04:06Z",
            },
        ),
        opted_in=True,
        sessions=system_ingest.SessionIndex.from_pid_map({"s1": [100]}),
    )

    assert problems == []
    assert [r.tool.name for r in records] == [
        "system:process-exec",
        "system:network-connect",
    ]
    network = records[1]
    assert network.session_id == "s1"
    assert network.tool.server == "93.184.216.34:443"
    for record in records:
        validate_record(record.to_dict())


def test_tracee_shape_maps() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        _tracee(
            {
                "eventName": "process_execve",
                "processId": 200,
                "parentProcessId": 1,
                "processName": "python",
                "timestamp": "2026-01-02T03:04:05Z",
                "session_id": "s2",
            },
            {
                "eventName": "net_connect",
                "processId": 201,
                "parentProcessId": 200,
                "processName": "curl",
                "dstIP": "1.2.3.4",
                "dstPort": 8443,
                "timestamp": "2026-01-02T03:04:06Z",
            },
        ),
        opted_in=True,
        sessions=system_ingest.SessionIndex.from_pid_map({"s2": [200]}),
    )

    assert problems == []
    assert [r.tool.name for r in records] == [
        "system:process-exec",
        "system:network-connect",
    ]
    assert records[1].session_id == "s2"
    assert records[1].tool.server == "1.2.3.4:8443"


def test_unmappable_event_is_quarantined_as_a_problem() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        _agentsight({"type": "mystery_event", "pid": 1}),
        opted_in=True,
    )
    assert records == []
    assert problems
    assert "unmappable" in problems[0].reason


def test_invalid_json_line_is_a_problem_not_a_crash() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        "not json", opted_in=True
    )
    assert records == []
    assert "invalid JSON" in problems[0].reason


# --- provenance / labeling ---------------------------------------------------


def test_every_record_is_labeled_source_system_ingest() -> None:
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "network_connect",
                "pid": 100,
                "ppid": 1,
                "comm": "node",
                "daddr": "1.2.3.4",
                "dport": 443,
                "timestamp": "2026-01-02T03:04:06Z",
                "session_id": "s1",
            }
        ),
        opted_in=True,
    )
    (record,) = records
    assert record.environment is not None
    assert record.environment["source"] == "system-ingest"
    assert record.harness == "system-ingest"
    assert record.producer is not None
    assert record.producer.kind is ProducerKind.INGEST
    assert record.producer.name == "system-ingest"
    assert system_ingest.is_system_ingest_record(record)


def test_unowned_lineage_is_not_attributed_to_a_session() -> None:
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "network_connect",
                "pid": 999,
                "ppid": 1,
                "comm": "sshd",
                "daddr": "9.9.9.9",
                "dport": 22,
                "timestamp": "2026-01-02T03:04:06Z",
            }
        ),
        opted_in=True,
        sessions=system_ingest.SessionIndex.from_pid_map({"s1": [100]}),
    )
    (record,) = records
    assert record.session_id == "unjoined:system-ingest"
    assert record.environment is not None
    assert record.environment["joined"] is False


def test_ambiguous_pid_ownership_is_not_joined() -> None:
    index = system_ingest.SessionIndex.from_pid_map({"s1": [100], "s2": [100]})
    assert index.owner_for(100) is None
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "process_exec",
                "pid": 100,
                "ppid": 1,
                "comm": "node",
                "timestamp": "2026-01-02T03:04:05Z",
            }
        ),
        opted_in=True,
        sessions=index,
    )
    assert records[0].session_id == "unjoined:system-ingest"


def test_event_outside_the_session_window_is_not_joined() -> None:
    sessions = system_ingest.SessionIndex.from_records([_pid_record("s1", 100, at=AT)])
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "process_exec",
                "pid": 100,
                "ppid": 1,
                "comm": "node",
                "timestamp": "2030-01-01T00:00:00Z",
            }
        ),
        opted_in=True,
        sessions=sessions,
    )
    assert records[0].session_id == "unjoined:system-ingest"


# --- false-join precision ----------------------------------------------------


def test_published_false_join_precision_matches_the_corpus() -> None:
    corpus = json.loads((FIXTURES / "lineage-corpus.json").read_text(encoding="utf-8"))
    index = system_ingest.SessionIndex.from_pid_map(corpus["session_pids"])
    records, problems = system_ingest.transcode_system_ingest(
        corpus["events"], opted_in=True, sessions=index
    )
    assert problems == []
    predicted = [
        r.session_id if not r.session_id.startswith("unjoined:") else None for r in records
    ]
    precision = system_ingest.join_precision(predicted, corpus["truth"])
    assert precision.precision == system_ingest.PUBLISHED_PRECISION["precision"]
    assert precision.recall == system_ingest.PUBLISHED_PRECISION["recall"]
    assert precision.false_joins == 0


# --- privacy / blast radius --------------------------------------------------


def test_secrets_are_masked_before_storage() -> None:
    cfg = RedactionConfig(mode=PrivacyMode.FULL, capture_tool_args=True)
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "process_exec",
                "pid": 100,
                "ppid": 1,
                "comm": "sh",
                "exe": "sh -c 'curl -H Authorization: sk-abcdefghij'",
                "timestamp": "2026-01-02T03:04:05Z",
            }
        ),
        opted_in=True,
        redaction=cfg,
    )
    (record,) = records
    assert record.tool.privacy_mode is RecordPrivacyMode.FULL
    assert "sk-abcdefghij" not in str(record.to_dict())
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED


def test_network_record_extends_impact_blast_radius(tmp_path: Path) -> None:
    sessions = system_ingest.SessionIndex.from_pid_map({"s1": [100]})
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "network_connect",
                "pid": 102,
                "ppid": 100,
                "comm": "node",
                "daddr": "93.184.216.34",
                "dport": 443,
                "timestamp": "2026-01-02T03:04:06Z",
            }
        ),
        opted_in=True,
        sessions=sessions,
    )
    assert any(fact.category == NETWORK for fact in classify_record(records[0]))

    store = RecordStore(tmp_path / "records.jsonl")
    for record in records:
        store.append(record)
    report = build_impact(store, "s1")
    assert report.network
    assert report.network[0].target == "93.184.216.34:443"


def test_run_system_ingest_appends_and_reports(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_pid_record("s1", 100, at=AT))
    source = tmp_path / "events.json"
    source.write_text(
        json.dumps(
            {
                "type": "network_connect",
                "pid": 102,
                "ppid": 100,
                "comm": "node",
                "daddr": "1.2.3.4",
                "dport": 443,
                "timestamp": "2026-01-02T03:04:06Z",
            }
        ),
        encoding="utf-8",
    )
    stats = system_ingest.run_system_ingest(
        [source],
        store,
        opted_in=True,
        sessions=system_ingest.SessionIndex.from_records(store.records()),
    )
    assert stats.records == 1
    assert [r.tool.name for r in store.records() if r.harness == "system-ingest"] == [
        "system:network-connect"
    ]


# --- branch coverage ---------------------------------------------------------


def test_join_precision_counts_false_joins_and_misses() -> None:
    precision = system_ingest.join_precision(["s1", None, "s2"], ["s2", "s1", "s2"])
    assert precision.false_joins == 1
    assert precision.missed == 1
    assert precision.precision == 0.5
    assert precision.recall == 0.5


def test_join_without_a_recorded_window_uses_lineage_only() -> None:
    sessions = system_ingest.SessionIndex(pid_owner={100: "s1"})
    records, _ = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "type": "process_exec",
                "pid": 100,
                "ppid": 1,
                "comm": "node",
                "timestamp": "2026-01-02T03:04:05Z",
            }
        ),
        opted_in=True,
        sessions=sessions,
    )
    assert records[0].session_id == "s1"


def test_event_without_a_timestamp_uses_now() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        _agentsight({"type": "process_exec", "pid": 1, "ppid": 1, "comm": "x"}),
        opted_in=True,
    )
    assert problems == []
    assert records[0].started_at.tzinfo is not None


def test_numeric_naive_and_invalid_timestamps() -> None:
    def _event(timestamp: Any) -> dict[str, Any]:
        return {"type": "process_exec", "pid": 1, "ppid": 1, "comm": "x", "timestamp": timestamp}

    epoch, problems = system_ingest.transcode_system_ingest(
        _agentsight(_event(1767323045)), opted_in=True
    )
    assert problems == []
    assert epoch[0].started_at.year == 2026
    nanos, problems = system_ingest.transcode_system_ingest(
        _agentsight(_event(1767323045000000000)), opted_in=True
    )
    assert problems == []
    naive, problems = system_ingest.transcode_system_ingest(
        _agentsight(_event("2026-01-02T03:04:05")), opted_in=True
    )
    assert problems == []
    assert naive[0].started_at.tzinfo is not None
    _records, problems = system_ingest.transcode_system_ingest(
        _agentsight(_event("not-a-date")), opted_in=True
    )
    assert problems and "invalid timestamp" in problems[0].reason


def test_tracee_cmdline_list_becomes_exe() -> None:
    records, problems = system_ingest.transcode_system_ingest(
        _agentsight(
            {
                "eventName": "process_execve",
                "processId": "100",
                "parentProcessId": "1",
                "processName": "sh",
                "cmdline": ["/bin/sh", "-c", "echo hi"],
                "timestamp": "2026-01-02T03:04:05Z",
            }
        ),
        opted_in=True,
    )
    assert problems == []
    assert records[0].agent.identity == "sh"


def test_malformed_events_are_problems_never_crashes() -> None:
    payload = [
        1,
        {"type": "process_exec"},
        {"type": "process_exec", "pid": True},
        {"type": "process_exec", "pid": "abc"},
    ]
    records, problems = system_ingest.transcode_system_ingest(payload, opted_in=True)
    assert records == []
    assert len(problems) == 4
    _records, problems = system_ingest.transcode_system_ingest(123, opted_in=True)
    assert "not events/list/object" in problems[0].reason


def test_run_system_ingest_requires_optin_and_handles_unreadable(
    tmp_path: Path,
) -> None:
    from agentwatch.quarantine import QuarantineLog

    store = RecordStore(tmp_path / "records.jsonl")
    with pytest.raises(system_ingest.SystemIngestNotOptedInError):
        system_ingest.run_system_ingest(
            [], store, opted_in=False, sessions=system_ingest.SessionIndex()
        )
    source = tmp_path / "events.json"
    source.write_text(
        json.dumps(
            [
                {"type": "mystery"},
                {
                    "type": "process_exec",
                    "pid": 7,
                    "ppid": 1,
                    "comm": "x",
                    "timestamp": "2026-01-02T03:04:05Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    stats = system_ingest.run_system_ingest(
        [source],
        store,
        opted_in=True,
        sessions=system_ingest.SessionIndex(),
        quarantine=QuarantineLog(tmp_path / "q.jsonl"),
    )
    assert stats.records == 1
    assert stats.problems
    second = system_ingest.run_system_ingest(
        [source, tmp_path / "missing.json"],
        store,
        opted_in=True,
        sessions=system_ingest.SessionIndex(),
    )
    assert second.duplicates == 1
    assert second.problems


def _pid_record(session: str, pid: int, *, at: datetime) -> Any:
    """A minimal hook record that anchors ``pid`` to ``session`` (test helper)."""
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall

    record = AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="claude-code"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=at,
        environment={"pid": pid},
    )
    validate_record(record.to_dict())
    return record


# --- conformance pack / CLI --------------------------------------------------


def test_conformance_pack_conforms() -> None:
    import sdk_conformance_registry  # noqa: F401  (registers the packs)

    from agentwatch import conformance

    report = conformance.run_sdk(sdk_conformance_registry.system_ingest_spec())
    assert report.ok, report.summary()
    assert "system-ingest" in {spec.name for spec in conformance.registered_sdks()}


def _events_file(tmp_path: Path) -> Path:
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps(
            {
                "type": "network_connect",
                "pid": 999,
                "ppid": 1,
                "comm": "sshd",
                "daddr": "1.2.3.4",
                "dport": 443,
                "timestamp": "2026-01-02T03:04:06Z",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_requires_consent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from agentwatch.cli.main import main

    rc = main(
        [
            "--set",
            f"store.path={tmp_path}",
            "ingest",
            str(_events_file(tmp_path)),
            "--format",
            "system-ingest",
        ]
    )

    assert rc != 0
    assert "consent" in capsys.readouterr().err


def test_cli_consent_ingests_unjoined_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentwatch.cli.main import main

    store_dir = tmp_path / "store"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "ingest",
            str(_events_file(tmp_path)),
            "--format",
            "system-ingest",
            "--consent",
            "--json",
        ]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["records"] == 1
    store = RecordStore(store_dir / "records.jsonl")
    assert [r.session_id for r in store.records()] == ["unjoined:system-ingest"]
