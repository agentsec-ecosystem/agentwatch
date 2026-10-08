"""Incident cases: merged, gap-annotated timeline + offline-verifiable bundle (M30 IR-1, #473).

PRD 57 §IR-1 / design ``docs/design/incident-cases.md``. Real incidents span
sessions/hosts/days; a case is a named, chain-recorded grouping of sessions with
a merged timeline (ordering rules stated, gaps classified) and a self-contained
bundle that re-verifies offline with no registry egress.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.incident_cases import (
    CASE_BUNDLE_FORMAT,
    CASE_TOOL,
    active_cases,
    build_case_bundle,
    case_markers,
    case_timeline,
    record_case_add,
    record_case_create,
    record_case_remove,
    render_case_timeline,
    verify_case_bundle,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)


def _record(
    session: str, *, at: datetime, tool: str = "Bash", project: str = "/repo"
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=at,
        project=project,
    )


def _seed(directory: Path) -> RecordStore:
    store = RecordStore(directory / "records.jsonl")
    store.append(_record("s1", at=NOW))
    store.append(_record("s2", at=NOW + timedelta(minutes=5)))
    # an explicit recording gap, then a > 1h jump across sessions
    store.append(_record("s2", at=NOW + timedelta(minutes=6), tool="recording-gap"))
    store.append(_record("s3", at=NOW + timedelta(hours=2, minutes=30)))
    return store


# --------------------------------------------------------------------------- membership


def test_case_create_is_a_chain_record(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    before = len(store.entries())
    case = record_case_create(store, title="prod regression", severity="high", ref="INC-1")
    assert case.case_id == "C1"
    assert case.title == "prod regression"
    entries = store.entries()
    assert len(entries) == before + 1
    assert entries[-1].record is not None
    assert entries[-1].record.tool.name == CASE_TOOL
    assert store.verify().ok


def test_membership_changes_are_chain_records(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session")
    before = len(store.entries())
    record_case_add(store, case.case_id, "s1")
    record_case_add(store, case.case_id, "s2")
    record_case_add(store, case.case_id, "s3")
    assert len(store.entries()) == before + 3
    assert store.verify().ok
    actions = [marker.action for marker in case_markers(store)]
    assert actions == ["create", "add", "add", "add"]
    (active,) = active_cases(store)
    assert [member.session_id for member in active.members] == ["s1", "s2", "s3"]


def test_case_remove_drops_membership(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session")
    record_case_add(store, case.case_id, "s1")
    record_case_add(store, case.case_id, "s2")
    removed = record_case_remove(store, case.case_id, "s1")
    assert removed.action == "remove"
    (active,) = active_cases(store)
    assert [member.session_id for member in active.members] == ["s2"]


def test_unknown_case_add_is_rejected(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    with pytest.raises(ValueError):
        record_case_add(store, "C99", "s1")


# --------------------------------------------------------------------------- timeline


def test_timeline_states_ordering_rules_and_merges_sessions(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session")
    for session in ("s2", "s1", "s3"):
        record_case_add(store, case.case_id, session)
    timeline = case_timeline(store, case.case_id)
    assert timeline.ordering
    assert "started_at" in timeline.ordering
    assert [entry.session_id for entry in timeline.entries] == ["s1", "s2", "s2", "s3"]


def test_timeline_classifies_time_and_explicit_gaps(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session")
    for session in ("s1", "s2", "s3"):
        record_case_add(store, case.case_id, session)
    timeline = case_timeline(store, case.case_id)
    kinds = {gap.kind for gap in timeline.gaps}
    assert "recording-gap" in kinds
    assert "time-gap" in kinds
    time_gap = next(gap for gap in timeline.gaps if gap.kind == "time-gap")
    assert time_gap.seconds is not None and time_gap.seconds > 3600


def test_timeline_is_not_materialized_for_non_members(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="one session")
    record_case_add(store, case.case_id, "s1")
    timeline = case_timeline(store, case.case_id)
    assert {entry.session_id for entry in timeline.entries} == {"s1"}


def test_render_timeline_states_rules_and_gaps(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session")
    for session in ("s1", "s2", "s3"):
        record_case_add(store, case.case_id, session)
    text = render_case_timeline(case_timeline(store, case.case_id))
    assert "ordering" in text.lower()
    assert "gap" in text.lower()


# --------------------------------------------------------------------------- bundle


def _build_and_write(tmp_path: Path) -> Path:
    store = _seed(tmp_path)
    case = record_case_create(store, title="multi-session", ref="INC-2")
    for session in ("s1", "s2", "s3"):
        record_case_add(store, case.case_id, session)
    bundle = build_case_bundle(store, case.case_id)
    out = tmp_path / "case.zip"
    bundle.write(out)
    return out


def test_case_bundle_verifies_offline(tmp_path: Path) -> None:
    out = _build_and_write(tmp_path)
    verification = verify_case_bundle(out)
    assert verification.bundle_format == CASE_BUNDLE_FORMAT
    assert verification.intact is True
    assert verification.problems == ()


def test_case_bundle_carries_verdict_table_and_report_shape(tmp_path: Path) -> None:
    out = _build_and_write(tmp_path)
    with zipfile.ZipFile(out) as archive:
        case_payload = json.loads(archive.read("case.json"))
        report = json.loads(archive.read("incident-report.json"))
    assert case_payload["ordering"]
    assert set(case_payload["verdicts"]) == {"s1", "s2", "s3"}
    assert report["submission"] == {
        "mode": "manual-voluntary",
        "endpoint": None,
        "auto_egress": False,
    }
    assert report["case_id"] == "C1"


def test_tampered_member_is_named_by_the_verifier(tmp_path: Path) -> None:
    out = _build_and_write(tmp_path)
    with zipfile.ZipFile(out) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["records.ndjson"] = members["records.ndjson"].replace(b'"Bash"', b'"BashX"')
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    verification = verify_case_bundle(out)
    assert verification.intact is False
    assert any("records.ndjson" in problem for problem in verification.problems)


def test_chain_tamper_is_caught_even_with_a_rehashed_manifest(tmp_path: Path) -> None:
    out = _build_and_write(tmp_path)
    with zipfile.ZipFile(out) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    # Rewrite the first chain row's payload but keep the manifest consistent:
    # member hashes pass, and the chain re-hash must still fail.
    lines = members["records.ndjson"].decode("utf-8").splitlines()
    row = json.loads(lines[0])
    row["record"]["tool"]["name"] = "Tampered"
    lines[0] = json.dumps(row, sort_keys=True, ensure_ascii=False)
    members["records.ndjson"] = ("\n".join(lines) + "\n").encode("utf-8")
    manifest = json.loads(members["manifest.json"])
    import hashlib

    manifest["members"]["records.ndjson"] = hashlib.sha256(
        members["records.ndjson"]
    ).hexdigest()
    members["manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    verification = verify_case_bundle(out)
    assert verification.intact is False
    assert any("chain" in problem for problem in verification.problems)


def test_unreadable_bundle_never_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    verification = verify_case_bundle(bad)
    assert verification.intact is False
    assert verification.problems


# --------------------------------------------------------------------------- CLI


def test_cli_case_lifecycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "case",
            "create",
            "--title",
            "prod regression",
            "--severity",
            "high",
            "--json",
        ]
    )
    assert rc == 0
    created = json.loads(capsys.readouterr().out)
    case_id = created["case_id"]

    for session in ("s1", "s2"):
        assert (
            main(
                [
                    "--set",
                    f"store.path={store_dir}",
                    "case",
                    "add",
                    case_id,
                    "--session",
                    session,
                    "--json",
                ]
            )
            == 0
        )
        capsys.readouterr()

    rc = main(["--set", f"store.path={store_dir}", "case", "show", case_id, "--json"])
    assert rc == 0
    shown = json.loads(capsys.readouterr().out)
    assert {entry["session_id"] for entry in shown["entries"]} == {"s1", "s2"}

    out = tmp_path / "case-bundle.zip"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "case",
            "export",
            case_id,
            "--out",
            str(out),
            "--json",
        ]
    )
    assert rc == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["case_id"] == case_id
    assert out.is_file()

    rc = main(["case", "verify", str(out), "--json"])
    assert rc == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["intact"] is True


def test_case_export_is_local_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _seed(store_dir)
    main(
        [
            "--set",
            f"store.path={store_dir}",
            "case",
            "create",
            "--title",
            "no egress",
            "--json",
        ]
    )
    case_id = json.loads(capsys.readouterr().out)["case_id"]
    out = tmp_path / "case.zip"
    main(
        [
            "--set",
            f"store.path={store_dir}",
            "case",
            "export",
            case_id,
            "--out",
            str(out),
            "--json",
        ]
    )
    capsys.readouterr()
    with zipfile.ZipFile(out) as archive:
        report = json.loads(archive.read("incident-report.json"))
    assert report["submission"]["auto_egress"] is False
    assert report["submission"]["endpoint"] is None
