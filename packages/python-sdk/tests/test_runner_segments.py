"""Sealed runner segments + ``import-segment`` + custody label (M30 RUN-1, #479).

PRD 58 §RUN-1, design ``docs/design/runner-segments.md``. An ephemeral/CI run
seals its records into a self-verifying segment (its **own** hash chain, runner
identity, start/end attestation). ``import-segment`` verifies the segment and
**anchors** it locally as a ``source: runner`` chain-of-custody record; imported
records are kept visibly weaker than locally-witnessed ones. Tampering fails;
no egress; a ``traceparent`` joins the runner session to its originating session.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.runner_segments import (
    SEGMENT_FORMAT,
    anchor_records,
    custody_rows,
    import_segment,
    render_custody,
    seal_segment,
    verify_segment,
)
from agentwatch.store import RecordStore
from agentwatch.trace_context import format_traceparent

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


def _record(
    session: str,
    *,
    at: datetime | None = None,
    tool: str = "Bash",
    traceparent: str | None = None,
    privacy: RecordPrivacyMode = RecordPrivacyMode.METADATA_ONLY,
) -> AgentRecord:
    record = AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool, arguments={"cmd": "ls"}, privacy_mode=privacy),
        outcome=Outcome.OK,
        started_at=at or START,
        harness="claude-code",
        traceparent=traceparent,
    )
    if traceparent is not None:
        from agentwatch.trace_context import parse_traceparent

        context = parse_traceparent(traceparent)
        if context is not None:
            record = replace(record, trace_id=context.trace_id, span_id=context.span_id)
    return record


def _runner_segment(tmp_path: Path) -> Path:
    records = [
        _record("runner-1", at=START),
        _record("runner-1", at=START + timedelta(seconds=5), tool="Read"),
    ]
    segment = seal_segment(
        records,
        runner="ci-runner-7",
        run_id="run-42",
        started_at=START,
        ended_at=START + timedelta(seconds=5),
    )
    out = tmp_path / "segment.zip"
    segment.write(out)
    return out


# --------------------------------------------------------------------------- sealing


def test_seal_writes_a_self_verifying_segment(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    verification = verify_segment(out)
    assert verification.bundle_format == SEGMENT_FORMAT
    assert verification.intact is True
    assert verification.attestation == "present"
    assert verification.runner == "ci-runner-7"
    assert verification.sessions == ("runner-1",)


def test_sealing_rejects_non_redacted_records(tmp_path: Path) -> None:
    records = [_record("runner-1", privacy=RecordPrivacyMode.FULL)]
    with pytest.raises(ValueError):
        seal_segment(
            records,
            runner="ci-runner-7",
            run_id="run-42",
            started_at=START,
            ended_at=START,
        )


def test_segment_has_its_own_chain_from_genesis(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    with zipfile.ZipFile(out) as archive:
        rows = [
            json.loads(line)
            for line in archive.read("records.ndjson").decode("utf-8").splitlines()
            if line.strip()
        ]
    assert rows[0]["prev_hash"] == "0" * 64
    assert [row["seq"] for row in rows] == [0, 1]


def test_tampered_member_fails(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    with zipfile.ZipFile(out) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["records.ndjson"] = members["records.ndjson"].replace(b'"Bash"', b'"BashX"')
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    verification = verify_segment(out)
    assert verification.intact is False
    assert any("records.ndjson" in problem for problem in verification.problems)


def test_rehashed_manifest_still_fails_on_the_chain(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    with zipfile.ZipFile(out) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    lines = members["records.ndjson"].decode("utf-8").splitlines()
    row = json.loads(lines[1])
    row["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(row, sort_keys=True, ensure_ascii=False)
    members["records.ndjson"] = ("\n".join(lines) + "\n").encode("utf-8")
    manifest = json.loads(members["manifest.json"])
    manifest["members"]["records.ndjson"] = hashlib.sha256(members["records.ndjson"]).hexdigest()
    members["manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    verification = verify_segment(out)
    assert verification.intact is False
    assert verification.first_broken == 1


def test_unreadable_segment_never_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    verification = verify_segment(bad)
    assert verification.intact is False
    assert verification.problems


# --------------------------------------------------------------------------- import / custody


def test_import_anchors_custody_and_is_chain_protected(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    store = RecordStore(tmp_path / "records.jsonl")
    report = import_segment(store, out)
    assert report.runner == "ci-runner-7"
    assert report.records == 2
    assert report.sessions == ("runner-1",)
    assert store.verify().ok
    anchors = anchor_records(store)
    assert anchors
    assert anchors[-1].action == "import"
    assert anchors[-1].runner == "ci-runner-7"


def test_imported_records_are_visibly_weaker_than_local(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("local-1"))
    import_segment(store, out)
    rows = {row.session_id: row for row in custody_rows(store)}
    assert rows["runner-1"].source == "runner"
    assert rows["runner-1"].locally_witnessed is False
    assert rows["runner-1"].chain_protected is True
    assert rows["local-1"].source == "local"
    assert rows["local-1"].locally_witnessed is True
    assert "NOT locally witnessed" in render_custody(store)


def test_tampered_segment_is_not_imported(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    with zipfile.ZipFile(out) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["records.ndjson"] = members["records.ndjson"].replace(b'"Bash"', b'"BashX"')
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])
    store = RecordStore(tmp_path / "records.jsonl")
    with pytest.raises(ValueError):
        import_segment(store, out)
    assert store.records() == []


def test_traceparent_joins_the_originating_session(tmp_path: Path) -> None:
    traceparent = format_traceparent(TRACE, "00f067aa0ba902b7")
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("local-1", traceparent=traceparent))
    records = [_record("runner-1", traceparent=traceparent)]
    segment = seal_segment(
        records,
        runner="ci-runner-7",
        run_id="run-42",
        started_at=START,
        ended_at=START,
        traceparent=traceparent,
    )
    out = tmp_path / "segment.zip"
    segment.write(out)

    report = import_segment(store, out)
    assert report.joined_sessions == ("local-1",)
    anchor = anchor_records(store)[-1]
    assert anchor.joined_sessions == ("local-1",)
    assert anchor.traceparent == traceparent


def test_segment_import_is_local_only(tmp_path: Path) -> None:
    out = _runner_segment(tmp_path)
    store = RecordStore(tmp_path / "records.jsonl")
    import_segment(store, out)
    anchor = anchor_records(store)[-1]
    assert anchor.auto_egress is False
    assert anchor.destination is None


# --------------------------------------------------------------------------- CLI


def test_cli_segment_export_import_and_verify_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record("runner-1"))
    store.append(_record("runner-1", tool="Read"))

    out = tmp_path / "segment.zip"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "segment",
            "export",
            "--session",
            "runner-1",
            "--runner",
            "ci-runner-7",
            "--run-id",
            "run-42",
            "--out",
            str(out),
            "--json",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    assert out.is_file()

    assert main(["segment", "verify", str(out), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["intact"] is True

    dest_dir = tmp_path / "imported"
    dest_dir.mkdir()
    rc = main(
        ["--set", f"store.path={dest_dir}", "import-segment", str(out), "--json"]
    )
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["runner"] == "ci-runner-7"

    assert main(["--set", f"store.path={dest_dir}", "verify-store"]) == 0
