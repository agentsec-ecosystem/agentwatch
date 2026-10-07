"""Retention profiles (M28 CMP-3, #360; PRD 44 §CMP-3).

Named retention profiles drive ``agentwatch retention apply`` so the window is a
policy choice, not a hand-edited number: ``high-risk-12mo`` (AAT §9),
``general-6mo``, and ``custom`` (the operator-configured window). A policy change
is a recorded chain event (S5), and a window whose retention has not been applied
degrades visibly rather than silently.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch import doctor
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
from agentwatch.recorder_state import last_state
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.retention import (
    CUSTOM_PROFILE,
    RETENTION_PROFILES,
    profile_names,
    resolve_retention_profile,
)
from agentwatch.store import RecordStore

NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def _cfg(store_dir: Path, *, retention_days: int = 30) -> AgentwatchConfig:
    return AgentwatchConfig(
        store=StoreSection(path=str(store_dir), retention_days=retention_days, max_size_mb=1024),
        privacy=PrivacySection(mode="metadata-only"),
        redaction=RedactionSection(self_test="enabled"),
        export=ExportSection(enabled=False, otlp_endpoint=None, format="otel-genai"),
        health=HealthSection(endpoint="127.0.0.1:9100"),
        log=LogSection(level="info"),
    )


def _record(*, days_ago: int) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=NOW - timedelta(days=days_ago),
    )


# --------------------------------------------------------------------------- profiles


def test_high_risk_profile_is_twelve_months() -> None:
    profile = resolve_retention_profile("high-risk-12mo", retention_days=30)

    assert profile.name == "high-risk-12mo"
    assert profile.retention_days == 365


def test_general_profile_is_six_months() -> None:
    profile = resolve_retention_profile("general-6mo", retention_days=30)

    assert profile.retention_days == 180


def test_custom_profile_uses_the_configured_window() -> None:
    profile = resolve_retention_profile(CUSTOM_PROFILE, retention_days=45)

    assert profile.name == CUSTOM_PROFILE
    assert profile.retention_days == 45


def test_default_profile_is_custom() -> None:
    profile = resolve_retention_profile(None, retention_days=45)

    assert profile.name == CUSTOM_PROFILE
    assert profile.retention_days == 45


def test_unknown_profile_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unknown retention profile"):
        resolve_retention_profile("forever", retention_days=30)


def test_registry_and_names_agree() -> None:
    assert set(profile_names()) == set(RETENTION_PROFILES) | {CUSTOM_PROFILE}


# --------------------------------------------------------------------------- apply


def test_cli_apply_profile_drives_the_window_and_records_the_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record(days_ago=400))  # older than 12mo
    store.append(_record(days_ago=10))  # inside 12mo

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "retention",
            "apply",
            "--profile",
            "high-risk-12mo",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "high-risk-12mo"
    assert payload["retention_days"] == 365

    reloaded = RecordStore(store_dir / "records.jsonl")
    assert reloaded.verify().ok is True
    state = last_state(reloaded)
    assert state.retention_profile == "high-risk-12mo"
    assert state.retention_days == 365


def test_custom_profile_uses_config_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl").append(_record(days_ago=10))

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "--set",
            "store.retention_days=7",
            "retention",
            "apply",
            "--profile",
            "custom",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["retention_days"] == 7


# --------------------------------------------------------------------------- visible


def test_doctor_warns_when_retention_was_not_applied(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl").append(_record(days_ago=400))

    results = doctor.run_checks(
        cfg=_cfg(store_dir, retention_days=30),
        store_path=store_dir / "records.jsonl",
        socket_path=tmp_path / "d.sock",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
    )

    retention = next(r for r in results if r.name == "retention")
    assert retention.status == doctor.WARN
    assert retention.hint is not None
    assert "retention apply" in retention.hint


def test_doctor_passes_when_everything_is_inside_the_window(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl").append(_record(days_ago=1))

    results = doctor.run_checks(
        cfg=_cfg(store_dir, retention_days=365),
        store_path=store_dir / "records.jsonl",
        socket_path=tmp_path / "d.sock",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
    )

    retention = next(r for r in results if r.name == "retention")
    assert retention.status == doctor.PASS


def test_compliance_report_cites_the_retention_profile(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record(days_ago=1))

    main(["--set", f"store.path={store_dir}", "retention", "apply", "--profile", "high-risk-12mo"])

    reloaded = RecordStore(store_dir / "records.jsonl")
    report = build_report(reloaded, "eu-ai-act-art12", config=_cfg(store_dir, retention_days=365))
    retention = next(row for row in report.controls if row.control == "art12-2-retention")

    assert retention.detail is not None
    assert "high-risk-12mo" in retention.detail
