"""Incident report export (M28 COR-3, #358; PRD 43 §COR-3).

``evidence <id> --include incident-report.json`` emits a registry-shaped, redacted
report alongside the bundle: findings mapped to the AIR schema + AIID GMF
taxonomy, operator annotations, and redaction receipts. It is **voluntary and
manual** — the report is only ever written into a local bundle; there is no
auto-egress path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from agentwatch.annotate import annotate_session
from agentwatch.cli.main import main
from agentwatch.egress_audit import audit
from agentwatch.evidence import build_bundle
from agentwatch.incident_report import (
    INCIDENT_REPORT_FILENAME,
    INCIDENT_REPORT_SCHEMA,
    build_incident_report,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schema" / "vectors" / "incident" / "incident-report.schema.json"
MODULE = Path(__file__).resolve().parents[1] / "src" / "agentwatch" / "incident_report.py"

AT = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)


def _record(name: str, *, outcome: Outcome = Outcome.OK, args: object = None) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=name, arguments=args),
        outcome=outcome,
        started_at=AT,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("Bash", args={"token": "sk-super-secret"}))
    store.append(_record("Bash", outcome=Outcome.DENIED))
    annotate_session(store, "s1", "reviewed", incident_tags=["prompt-injection"])
    return store


def _validate(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)


# --------------------------------------------------------------------------- build


def test_report_is_schema_shaped(tmp_path: Path) -> None:
    report = build_incident_report(_store(tmp_path), "s1", now=AT)

    assert report["schema"] == INCIDENT_REPORT_SCHEMA
    _validate(report)


def test_denied_record_is_mapped_to_air_and_gmf(tmp_path: Path) -> None:
    report = build_incident_report(_store(tmp_path), "s1", now=AT)

    denied = [finding for finding in report["findings"] if finding["event"] == "denied"]
    assert len(denied) == 1
    assert denied[0]["air"]["control"] == "access-control"
    assert denied[0]["gmf"] == "Misuse"


def test_incident_tags_survive_as_annotations(tmp_path: Path) -> None:
    report = build_incident_report(_store(tmp_path), "s1", now=AT)

    assert report["annotations"][0]["incident_tags"] == ["prompt-injection"]


def test_report_never_carries_tool_arguments(tmp_path: Path) -> None:
    report = build_incident_report(_store(tmp_path), "s1", now=AT)

    blob = json.dumps(report)
    assert "sk-super-secret" not in blob
    assert report["redaction"]["arguments_included"] is False
    assert report["submission"]["auto_egress"] is False


# --------------------------------------------------------------------------- bundle


def test_evidence_include_adds_the_report_member(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store_dir = tmp_path

    bundle = build_bundle(
        store,
        store_dir / "records.jsonl",
        "s1",
        includes=(INCIDENT_REPORT_FILENAME,),
        now=AT,
    )

    assert INCIDENT_REPORT_FILENAME in bundle.members
    _validate(json.loads(bundle.members[INCIDENT_REPORT_FILENAME]))


def test_cli_evidence_include_writes_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)
    out = tmp_path / "bundle.zip"

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "evidence",
            "s1",
            "--include",
            INCIDENT_REPORT_FILENAME,
            "--out",
            str(out),
        ]
    )
    capsys.readouterr()

    assert rc == 0
    import zipfile

    with zipfile.ZipFile(out) as archive:
        _validate(json.loads(archive.read(INCIDENT_REPORT_FILENAME)))


def test_unknown_include_fails_loudly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "evidence", "s1", "--include", "nope.json"])
    err = capsys.readouterr().err

    assert rc != 0
    assert "unknown include" in err


# --------------------------------------------------------------------------- egress


def test_module_has_no_egress_path(tmp_path: Path) -> None:
    import shutil

    shutil.copy(MODULE, tmp_path / MODULE.name)
    assert audit(tmp_path) == []
