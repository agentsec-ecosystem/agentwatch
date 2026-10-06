"""Compliance report engine tests (M26 CMP-1, #326).

Every row is control -> evidence command -> verdict -> refs, computed offline;
retention and signature status are surfaced; the report never certifies.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.compliance import build_report, render_report
from agentwatch.configuration import AgentwatchConfig
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _record(started: datetime) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker", principal="human@corp.example"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=started,
    )


def _config(*, retention_days: int = 365, checkpoint_every: int | None = 100) -> AgentwatchConfig:
    cfg = AgentwatchConfig()
    return replace(
        cfg,
        store=replace(
            cfg.store, retention_days=retention_days, checkpoint_every=checkpoint_every
        ),
        privacy=replace(cfg.privacy, mode="metadata-only"),
    )


def _store(tmp_path: Path, *, days_old: int = 1) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record(NOW - timedelta(days=days_old)))
    return store


def test_report_rows_have_control_evidence_and_verdict(tmp_path: Path) -> None:
    report = build_report(
        _store(tmp_path), "eu-ai-act-art12", config=_config(), now=NOW
    )

    assert report.framework == "eu-ai-act-art12"
    assert report.controls
    for control in report.controls:
        assert control.control
        assert control.evidence.startswith("agentwatch ")
        assert control.verdict in {"pass", "fail", "unknown"}
        assert control.refs


def test_log_integrity_passes_on_an_intact_chain(tmp_path: Path) -> None:
    report = build_report(_store(tmp_path), "generic", config=_config(), now=NOW)

    integrity = next(c for c in report.controls if c.control == "log-integrity")
    assert integrity.verdict == "pass"
    assert integrity.evidence == "agentwatch verify-store"


def test_full_privacy_mode_fails_the_redaction_control(tmp_path: Path) -> None:
    cfg = replace(_config(), privacy=replace(_config().privacy, mode="full"))

    report = build_report(_store(tmp_path), "generic", config=cfg, now=NOW)

    redaction = next(c for c in report.controls if c.control == "redaction-default")
    assert redaction.verdict == "fail"


def test_overdue_retention_degrades_visibly(tmp_path: Path) -> None:
    report = build_report(
        _store(tmp_path, days_old=400), "generic", config=_config(retention_days=365), now=NOW
    )

    assert report.retention.status == "overdue"
    assert report.retention.retention_days == 365


def test_signature_status_is_honest_and_never_certifies(tmp_path: Path) -> None:
    report = build_report(_store(tmp_path), "soc2", config=_config(), now=NOW)

    assert report.signature.signed is False
    assert "opt-in" in report.signature.detail or "not enabled" in report.signature.detail
    assert "not a certification" in report.statement.lower()


def test_report_render_and_json(tmp_path: Path) -> None:
    report = build_report(_store(tmp_path), "iso-42001", config=_config(), now=NOW)

    payload = report.to_dict()
    json.dumps(payload)
    assert payload["framework"] == "iso-42001"
    assert "agentwatch compliance" in render_report(report)


def test_cli_compliance_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    from agentwatch.cli.main import main

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "compliance",
            "report",
            "--framework",
            "eu-ai-act-art12",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["framework"] == "eu-ai-act-art12"
    assert payload["controls"]
