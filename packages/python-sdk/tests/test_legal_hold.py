"""Legal hold suspends retention/purge, with override provenance (M29 HLD-1, #450).

PRD 56 §HLD-1: ``hold add/list/release`` on a scope (session/project/time/principal);
while a hold is active ``retention apply`` skips held records and ``purge`` fails
closed unless an explicit, recorded override with a reason is given. Holds, releases,
and overrides are hash-chain records; D-K tombstone semantics are preserved.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.compliance import build_report
from agentwatch.configuration import (
    AgentwatchConfig,
    ExportSection,
    HealthSection,
    LogSection,
    PrivacySection,
    RedactionSection,
    StoreSection,
)
from agentwatch.evidence import build_bundle
from agentwatch.holds import (
    Hold,
    HoldKind,
    active_holds,
    held_hold_ids,
    hold_records,
    parse_scope,
    record_hold_add,
    record_hold_release,
    record_matches_hold,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _record(session: str, *, days_ago: int, project: str | None = None) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=NOW - timedelta(days=days_ago),
        project=project,
    )


def _seed(directory: Path) -> RecordStore:
    store = RecordStore(directory / "records.jsonl")
    store.append(_record("s1", days_ago=100))
    store.append(_record("s2", days_ago=100))
    store.append(_record("s3", days_ago=1))
    return store


def _config(directory: Path) -> AgentwatchConfig:
    return AgentwatchConfig(
        store=StoreSection(path=str(directory), retention_days=30, max_size_mb=1024),
        privacy=PrivacySection(mode="metadata-only"),
        redaction=RedactionSection(self_test="enabled"),
        export=ExportSection(enabled=False, otlp_endpoint=None, format="otel-genai"),
        health=HealthSection(endpoint="127.0.0.1:9100"),
        log=LogSection(level="info"),
    )


# --------------------------------------------------------------------------- scope


def test_parse_scope_supports_every_documented_scope() -> None:
    assert parse_scope("session:s1").kind is HoldKind.SESSION
    assert parse_scope("project:/work/x").value == "/work/x"
    assert parse_scope("principal:alice").value == "alice"
    window = parse_scope("time:2026-01-01T00:00:00+00:00..2026-02-01T00:00:00+00:00")
    assert window.kind is HoldKind.TIME
    assert window.start is not None and window.end is not None

    with pytest.raises(ValueError, match="hold scope"):
        parse_scope("bogus")


# --------------------------------------------------------------------------- chain


def test_parse_scope_rejects_malformed_time_and_unknown_kind() -> None:
    for bad in (
        "time:2026-01-01",
        "time:not-a-date..2026-01-01T00:00:00+00:00",
        "time:2026-02-01T00:00:00+00:00..2026-01-01T00:00:00+00:00",
        "team:blue",
    ):
        with pytest.raises(ValueError, match="hold scope"):
            parse_scope(bad)


def test_project_principal_and_time_scopes_match() -> None:
    record = _record("s1", days_ago=1, project="/work/x")
    principal = replace(record, agent=AgentIdentity(identity="agent", principal="hmac:alice"))
    window = parse_scope("time:2026-01-01T00:00:00+00:00..2026-12-31T00:00:00+00:00")

    assert window.label().startswith("time:")
    assert record_matches_hold(record, Hold("H1", parse_scope("project:/work/x"), "r", None, NOW, 1))
    assert record_matches_hold(principal, Hold("H2", parse_scope("principal:hmac:alice"), "r", None, NOW, 2))
    assert record_matches_hold(record, Hold("H3", window, "r", None, NOW, 3))
    assert not record_matches_hold(record, Hold("H4", parse_scope("project:/other"), "r", None, NOW, 4))
    outside = replace(record, started_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert not record_matches_hold(outside, Hold("H5", window, "r", None, NOW, 5))


def test_hold_records_serialize_for_reports(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    record_hold_add(store, parse_scope("session:s1"), reason="litigation", ref="CASE-1")

    payload = hold_records(store)[0].to_dict()

    assert payload["action"] == "add"
    assert payload["scope"] == "session:s1"
    assert payload["ref"] == "CASE-1"


def test_hold_add_and_release_are_chain_records(tmp_path: Path) -> None:
    store = _seed(tmp_path)

    hold = record_hold_add(
        store, parse_scope("session:s1"), reason="litigation", ref="CASE-1"
    )

    assert hold.hold_id.startswith("H")
    assert [entry.hold_id for entry in active_holds(store)] == [hold.hold_id]
    assert store.verify().ok
    assert any(entry.action == "add" for entry in hold_records(store))

    released = record_hold_release(store, hold.hold_id, reason="matter closed")

    assert released is not None
    assert active_holds(store) == []
    assert store.verify().ok


def test_releasing_an_unknown_hold_is_a_noop(tmp_path: Path) -> None:
    store = _seed(tmp_path)

    assert record_hold_release(store, "H999") is None
    assert active_holds(store) == []


# --------------------------------------------------------------------------- retention


def test_retention_skips_held_records(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    hold = record_hold_add(store, parse_scope("session:s1"), reason="litigation")

    report = store.apply_retention(retention_days=30, now=NOW)

    assert report.purged == 1  # s2 only
    assert report.held == 1  # s1 protected
    reloaded = RecordStore(tmp_path / "records.jsonl")
    survivors = {record.session_id for record in reloaded.records()}
    assert "s1" in survivors
    assert "s2" not in survivors
    assert reloaded.verify().ok
    # the hold protects the record across a rebuild from the chain
    assert held_hold_ids(next(r for r in reloaded.records() if r.session_id == "s1"), active_holds(reloaded)) == (
        hold.hold_id,
    )


# --------------------------------------------------------------------------- purge


def test_purge_fails_closed_on_a_held_session_and_records_the_refusal(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    hold = record_hold_add(
        store, parse_scope("session:s1"), reason="litigation", ref="CASE-1"
    )

    report = store.purge_session("s1")

    assert report.found is True
    assert report.purged == 0
    assert report.blocked_by_hold == hold.hold_id
    assert report.override_required is True
    assert any(record.session_id == "s1" and record.tool.name == "Bash" for record in store.records())
    assert store.verify().ok
    blocked = [marker for marker in hold_records(store) if marker.action == "purge-blocked"]
    assert blocked and blocked[0].hold_id == hold.hold_id


def test_purge_override_requires_a_reason_and_is_conspicuous(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    record_hold_add(store, parse_scope("session:s1"), reason="litigation", ref="CASE-1")

    before = store.purge_session("s1")
    assert before.purged == 0

    report = store.purge_session("s1", override_reason="court order 2026-10-06")

    assert report.purged == 2
    assert report.override_reason == "court order 2026-10-06"
    assert store.verify().ok
    overrides = [marker for marker in hold_records(store) if marker.action == "purge-override"]
    assert len(overrides) == 1
    assert overrides[0].reason == "court order 2026-10-06"

    bundle = build_bundle(store, tmp_path / "records.jsonl", "s1")
    rows = [
        json.loads(line)
        for line in bundle.members["records.ndjson"].decode("utf-8").splitlines()
        if line
    ]
    assert any(row["record"]["tool"]["name"] == "legal-hold" for row in rows)


def test_a_session_without_a_hold_purges_normally(tmp_path: Path) -> None:
    store = _seed(tmp_path)

    report = store.purge_session("s2")

    assert report.purged == 1
    assert report.blocked_by_hold is None
    assert not any(record.session_id == "s2" and record.tool.name == "Bash" for record in store.records())


# --------------------------------------------------------------------------- report


def test_compliance_report_lists_holds_and_overrides(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    record_hold_add(store, parse_scope("session:s1"), reason="litigation")
    store.purge_session("s1", override_reason="court order")

    report = build_report(store, "generic", config=_config(tmp_path))

    assert report.retention is not None
    assert report.retention.holds == 1
    assert report.retention.overrides == 1
    assert "hold" in report.retention.detail.lower()


# --------------------------------------------------------------------------- cli


def test_cli_hold_add_list_release(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "hold",
            "add",
            "--scope",
            "session:s1",
            "--reason",
            "litigation",
            "--ref",
            "CASE-1",
            "--json",
        ]
    )
    assert rc == 0
    added = json.loads(capsys.readouterr().out)
    hold_id = added["hold_id"]
    assert added["scope"] == "session:s1"

    rc = main(["--set", f"store.path={store_dir}", "hold", "list", "--json"])
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert [entry["hold_id"] for entry in listed["holds"]] == [hold_id]

    rc = main(["--set", f"store.path={store_dir}", "hold", "release", hold_id, "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["released"] == hold_id


def test_cli_hold_list_renders_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)
    main(
        [
            "--set",
            f"store.path={store_dir}",
            "hold",
            "add",
            "--scope",
            "session:s1",
            "--reason",
            "litigation",
        ]
    )
    capsys.readouterr()

    rc = main(["--set", f"store.path={store_dir}", "hold", "list"])

    assert rc == 0
    assert "active hold" in capsys.readouterr().out

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    rc = main(["--set", f"store.path={empty_dir}", "hold", "list"])

    assert rc == 0
    assert "0 active hold" in capsys.readouterr().out


def test_cli_purge_fails_closed_then_allows_a_recorded_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)
    main(
        [
            "--set",
            f"store.path={store_dir}",
            "hold",
            "add",
            "--scope",
            "session:s1",
            "--reason",
            "litigation",
        ]
    )
    capsys.readouterr()

    rc = main(["--set", f"store.path={store_dir}", "purge", "s1", "--yes"])

    assert rc != 0
    assert "hold" in capsys.readouterr().err.lower()
    assert any(
        record.session_id == "s1" and record.tool.name == "Bash"
        for record in RecordStore(store_dir / "records.jsonl").records()
    )

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "purge",
            "s1",
            "--yes",
            "--override-reason",
            "court order 2026-10-06",
        ]
    )
    assert rc == 0
    assert "override" in capsys.readouterr().out.lower()


def test_cli_retention_dry_run_lists_skipped_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)
    main(
        [
            "--set",
            f"store.path={store_dir}",
            "hold",
            "add",
            "--scope",
            "session:s1",
            "--reason",
            "litigation",
        ]
    )
    capsys.readouterr()

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "--set",
            "store.retention_days=30",
            "retention",
            "apply",
            "--dry-run",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["held"] == 1
    assert payload["skipped"][0]["session_id"] == "s1"
    assert payload["skipped"][0]["hold_ids"]
    # nothing was tombstoned
    assert not any(
        entry.tombstone for entry in RecordStore(store_dir / "records.jsonl").entries()
    )
