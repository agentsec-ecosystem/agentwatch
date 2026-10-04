"""Evidence-bundle tests (M15 S1, #231).

A bundle verifies offline with no store; the three verdicts (intact / complete /
leak-free) are independent; a tampered member fails.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.evidence import (
    BUNDLE_FORMAT,
    EvidenceBundle,
    build_bundle,
    verify_bundle,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    Producer,
    ProducerKind,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.store_access import store_accesses

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    session: str = "s1",
    tool: str = "Bash",
    project: str | None = "/repo/secret",
    parent: str | None = None,
    producer: Producer | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool, arguments={"cmd": "ls"}),
        outcome=Outcome.OK,
        started_at=START,
        harness="claude-code",
        project=project,
        parent_session_id=parent,
        producer=producer,
    )


def _store(tmp_path: Path) -> tuple[RecordStore, Path]:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record())
    store.append(_record(tool="Read"))
    return store, path


def test_bundle_round_trips_offline(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    bundle = build_bundle(store, path, "s1")
    out = tmp_path / "s1.zip"
    bundle.write(out)

    verification = verify_bundle(out)

    assert verification.ok
    assert verification.intact and verification.complete and verification.leak_free
    assert verification.bundle_format == BUNDLE_FORMAT


def test_bundle_members_are_present(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    bundle = build_bundle(store, path, "s1")

    for name in (
        "manifest.json",
        "records.ndjson",
        "chain.json",
        "verify.json",
        "verify.txt",
        "privacy.json",
        "coverage.json",
        "inventory.json",
        "findings.json",
        "summary.md",
    ):
        assert name in bundle.members
    assert any(name.startswith("SCHEMA/") for name in bundle.members)


def test_include_bom_adds_the_cyclonedx_member(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    without = build_bundle(store, path, "s1")
    with_bom = build_bundle(store, path, "s1", include_bom=True)

    assert "bom.cdx.json" not in without.members
    assert "bom.cdx.json" in with_bom.members
    assert json.loads(with_bom.members["bom.cdx.json"])["bomFormat"] == "CycloneDX"


def test_tampered_member_fails_verification(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    bundle = build_bundle(store, path, "s1")
    members = dict(bundle.members)
    members["records.ndjson"] = members["records.ndjson"] + b"{}"
    tampered = EvidenceBundle(session_id="s1", members=members)
    out = tmp_path / "tampered.zip"
    tampered.write(out)

    verification = verify_bundle(out)

    assert not verification.ok
    assert not verification.intact
    assert any("tampered" in problem for problem in verification.problems)


def test_unknown_bundle_format_is_rejected_and_named(tmp_path: Path) -> None:
    out = tmp_path / "weird.zip"
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"bundle_format": "agentwatch-evidence/999"}))

    verification = verify_bundle(out)

    assert not verification.intact
    assert any("agentwatch-evidence/999" in problem for problem in verification.problems)


def test_purged_session_bundle_still_verifies_and_says_so(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    store.purge_session("s1")

    bundle = build_bundle(store, path, "s1")
    out = tmp_path / "s1.zip"
    bundle.write(out)

    verification = verify_bundle(out)
    coverage = json.loads(bundle.members["coverage.json"])
    assert verification.ok
    assert coverage["purges"]  # the purge is enumerated, not hidden
    assert coverage["tombstones"]


def test_resumed_session_reports_linked_ids(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(session="child", parent="parent"))

    bundle = build_bundle(store, tmp_path / "records.jsonl", "child")

    verify_json = json.loads(bundle.members["verify.json"])
    assert verify_json["linked_sessions"] == ["parent"]


def test_redact_paths_masks_project(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    bundle = build_bundle(store, path, "s1", redact_paths=True)

    rows = [json.loads(line) for line in bundle.members["records.ndjson"].decode().splitlines()]
    assert all(row["record"]["project"] == "<REDACTED:path>" for row in rows)


def test_broken_chain_bundle_carries_the_verdict(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    text = path.read_text(encoding="utf-8")
    tampered = text.replace('"tool": {"name": "Bash"', '"tool": {"name": "Evil"', 1)
    path.write_text(tampered, encoding="utf-8")

    bundle = build_bundle(RecordStore(path), path, "s1")
    out = tmp_path / "s1.zip"
    bundle.write(out)

    verification = verify_bundle(out)
    assert verification.intact is False  # never implies intactness


def test_cli_evidence_create_and_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)
    out = tmp_path / "bundle.zip"

    rc = main(["--set", f"store.path={store_dir}", "evidence", "s1", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    capsys.readouterr()

    rc = main(["evidence", "verify", str(out)])
    assert rc == 0
    out_text = capsys.readouterr().out
    assert "intact    : True" in out_text
    assert "complete  : True" in out_text
    assert "leak-free : True" in out_text

    accesses = store_accesses(RecordStore(store_dir / "records.jsonl"))
    assert [a.command for a in accesses] == ["evidence"]


def test_missing_session_is_rejected(tmp_path: Path) -> None:
    store, path = _store(tmp_path)

    with pytest.raises(ValueError):
        build_bundle(store, path, "does-not-exist")


def test_recording_gap_makes_the_bundle_incomplete(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    store.append(_record(tool="recording-gap"))

    bundle = build_bundle(store, path, "s1")
    coverage = json.loads(bundle.members["coverage.json"])

    assert coverage["gaps"]
    assert coverage["complete"] is False


def test_coverage_reports_per_producer_counts(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(producer=Producer(kind=ProducerKind.IMPORT, name="transcript")))
    store.append(_record(producer=Producer(kind=ProducerKind.HOOK, name="claude-code")))

    bundle = build_bundle(store, path, "s1")
    coverage = json.loads(bundle.members["coverage.json"])

    assert coverage["producers"] == {"hook": 1, "import": 1}


def test_bundle_includes_operator_notes_as_findings(tmp_path: Path) -> None:
    from agentwatch.annotate import annotate_session

    store, path = _store(tmp_path)
    annotate_session(store, "s1", "root cause was a retry storm", tag="reviewed")

    bundle = build_bundle(store, path, "s1")
    findings = json.loads(bundle.members["findings.json"])
    summary = bundle.members["summary.md"].decode("utf-8")

    assert findings[0]["note"] == "root cause was a retry storm"
    assert findings[0]["tag"] == "reviewed"
    assert "## Findings" in summary
    assert "root cause was a retry storm" in summary


def test_coverage_ignores_tombstoned_entries(tmp_path: Path) -> None:
    from agentwatch.evidence import _coverage

    store, _ = _store(tmp_path)
    store.purge_session("s1")

    coverage = _coverage(store, "s1", store.entries())

    assert coverage["tombstones"]
    assert coverage["purges"]


def test_bundle_includes_nearest_checkpoints(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(session="pre"))
    store.checkpoint()
    store.append(_record())
    store.checkpoint()

    bundle = build_bundle(store, path, "s1")
    chain = json.loads(bundle.members["chain.json"])

    assert chain["checkpoints"]["anchors_available"] is True
    assert chain["checkpoints"]["before"]["seq"] == 1
    assert chain["checkpoints"]["after"]["seq"] == 3


def test_bundle_without_a_later_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record(session="pre"))
    store.checkpoint()
    store.append(_record())

    bundle = build_bundle(store, path, "s1")
    chain = json.loads(bundle.members["chain.json"])

    assert chain["checkpoints"]["before"]["seq"] == 1
    assert chain["checkpoints"]["after"] is None


def test_bundle_without_schema_dir_omits_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, path = _store(tmp_path)
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    bundle = build_bundle(store, path, "s1")

    assert not any(name.startswith("SCHEMA/") for name in bundle.members)


def test_redact_paths_masks_nested_lists(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="agent"),
            tool=ToolCall(name="Read", arguments={"files": ["/etc/passwd"], "count": 3}),
            outcome=Outcome.OK,
            started_at=START,
        )
    )

    bundle = build_bundle(store, path, "s1", redact_paths=True)
    rows = [json.loads(line) for line in bundle.members["records.ndjson"].decode().splitlines()]

    assert rows[0]["record"]["tool"]["arguments"]["files"] == ["<REDACTED:path>"]


def test_verification_to_dict(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    out = tmp_path / "s1.zip"
    build_bundle(store, path, "s1").write(out)

    payload = verify_bundle(out).to_dict()

    assert payload["bundle_format"] == BUNDLE_FORMAT
    assert payload["intact"] is True
    assert payload["problems"] == []


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    out = tmp_path / "no-manifest.zip"
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("records.ndjson", "")

    verification = verify_bundle(out)

    assert not verification.intact
    assert verification.problems == ("manifest.json missing",)


def test_manifest_listing_a_missing_member_fails(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    members = dict(build_bundle(store, path, "s1").members)
    manifest = json.loads(members["manifest.json"])
    manifest["members"]["ghost.txt"] = "0" * 64
    members["manifest.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    out = tmp_path / "ghost.zip"
    EvidenceBundle(session_id="s1", members=members).write(out)

    verification = verify_bundle(out)

    assert not verification.intact
    assert any("member missing: ghost.txt" in problem for problem in verification.problems)


def test_unreadable_coverage_member_is_reported(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    members = dict(build_bundle(store, path, "s1").members)
    del members["coverage.json"]
    out = tmp_path / "no-coverage.zip"
    EvidenceBundle(session_id="s1", members=members).write(out)

    verification = verify_bundle(out)

    assert any("member missing: coverage.json" in problem for problem in verification.problems)
    assert any("coverage.json unreadable" in problem for problem in verification.problems)


def test_unreadable_bundle_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip", encoding="utf-8")

    verification = verify_bundle(bad)

    assert not verification.intact
    assert any("unreadable bundle" in problem for problem in verification.problems)


def test_blank_lines_in_the_segment_are_ignored(tmp_path: Path) -> None:
    store, path = _store(tmp_path)
    members = dict(build_bundle(store, path, "s1").members)
    members["records.ndjson"] = members["records.ndjson"] + b"\n"
    out = tmp_path / "blank-line.zip"
    EvidenceBundle(session_id="s1", members=members).write(out)

    verification = verify_bundle(out)

    # The blank line parses (the segment stays intact) but the member hash no longer matches.
    assert any("tampered" in problem for problem in verification.problems)
