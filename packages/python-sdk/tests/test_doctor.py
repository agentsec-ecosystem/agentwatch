"""Tests for ``agentwatch doctor`` (M5 C1, #175; PRD 22 C1).

An ordered checklist that turns a silent first-run failure into an actionable
message: every check reports PASS/WARN/FAIL with a one-line fix hint, ``--json``
emits the same data, and the command exits non-zero only on a FAIL.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch import doctor
from agentwatch.configuration import (
    AgentwatchConfig,
    ExportSection,
    HealthSection,
    LogSection,
    PrivacySection,
    RedactionSection,
    StoreSection,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore


def _cfg(**overrides: object) -> AgentwatchConfig:
    store = overrides.pop(
        "store", StoreSection(path="~/.local/share/agentwatch", retention_days=30, max_size_mb=1024)
    )
    return AgentwatchConfig(
        store=store,  # type: ignore[arg-type]
        privacy=PrivacySection(mode="metadata-only"),
        redaction=RedactionSection(self_test="enabled"),
        export=ExportSection(enabled=False, otlp_endpoint=None, format="otel-genai"),
        health=HealthSection(endpoint="127.0.0.1:9100"),
        log=LogSection(level="info"),
        **overrides,  # type: ignore[arg-type]
    )


def _write_hooks(settings: Path) -> None:
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/opt/aw/bin/agentwatch-hook",
                                    "args": ["pre"],
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def _store_with_record(tmp_path: Path) -> Path:
    path = tmp_path / "records.jsonl"
    RecordStore(path).append(
        AgentRecord(
            session_id="s",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )
    return path


def _statuses(results: list[doctor.CheckResult]) -> dict[str, str]:
    return {result.name: result.status for result in results}


def test_check_order_and_names() -> None:
    assert [name for name, _ in doctor.CHECKS] == [
        "config",
        "hooks",
        "daemon",
        "hook-entrypoint",
        "store-chain",
        "redaction-self-test",
        "store-disk",
        "retention",
        "harness-drift",
        "version",
    ]


def test_all_green_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    _write_hooks(settings)
    monkeypatch.setattr(doctor, "is_daemon_alive", lambda *a, **k: True)

    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=_store_with_record(tmp_path),
        socket_path=tmp_path / "d.sock",
        settings_paths={"project": settings, "user": tmp_path / "none.json"},
        executable=sys.executable,
    )

    statuses = _statuses(results)
    assert set(statuses.values()) <= {"PASS", "WARN"}
    assert statuses["daemon"] == "PASS"
    assert statuses["store-chain"] == "PASS"
    assert statuses["redaction-self-test"] == "PASS"
    assert doctor.all_passed(results) is True


def test_daemon_down_is_fail_with_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "is_daemon_alive", lambda *a, **k: False)

    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    daemon_check = next(r for r in results if r.name == "daemon")
    assert daemon_check.status == "FAIL"
    assert daemon_check.hint is not None
    assert "init" in daemon_check.hint
    assert doctor.all_passed(results) is False


def test_no_store_is_pass_with_note(tmp_path: Path) -> None:
    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    store_check = next(r for r in results if r.name == "store-chain")
    assert store_check.status == "PASS"
    assert "no records" in store_check.detail.lower()


def test_broken_chain_is_fail(tmp_path: Path) -> None:
    path = _store_with_record(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(envelope)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=path,
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    store_check = next(r for r in results if r.name == "store-chain")
    assert store_check.status == "FAIL"
    assert store_check.hint is not None


def test_hooks_absent_is_warn_with_hint(tmp_path: Path) -> None:
    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    hooks_check = next(r for r in results if r.name == "hooks")
    assert hooks_check.status == "WARN"
    assert hooks_check.hint is not None


def test_hooks_in_both_scopes_is_warn(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    user = tmp_path / "user.json"
    _write_hooks(project)
    _write_hooks(user)

    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": project, "user": user},
        executable=sys.executable,
    )

    hooks_check = next(r for r in results if r.name == "hooks")
    assert hooks_check.status == "WARN"
    assert "both" in hooks_check.detail.lower()


def test_missing_hook_entrypoint_is_fail(tmp_path: Path) -> None:
    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable="/nonexistent/python",
    )

    entry = next(r for r in results if r.name == "hook-entrypoint")
    assert entry.status == "FAIL"


def test_redaction_self_test_failure_is_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agentwatch.selftest import SelfTestResult

    monkeypatch.setattr(
        doctor,
        "run_redaction_self_test",
        lambda cfg=None: SelfTestResult(passed=False, checked=1, leaks=("sk-LEAK",)),
    )

    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    redaction = next(r for r in results if r.name == "redaction-self-test")
    assert redaction.status == "FAIL"
    # The failing check never echoes the leaked value.
    assert "sk-LEAK" not in redaction.detail
    assert redaction.hint is not None


def test_insane_retention_is_fail(tmp_path: Path) -> None:
    cfg = _cfg(store=StoreSection(path=str(tmp_path), retention_days=0, max_size_mb=1024))

    results = doctor.run_checks(
        cfg=cfg,
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    retention = next(r for r in results if r.name == "retention")
    assert retention.status == "FAIL"


def test_disk_cap_exceeds_free_space_is_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr("shutil.disk_usage", lambda path: Usage(total=1, used=1, free=10))
    cfg = _cfg(store=StoreSection(path=str(tmp_path), retention_days=30, max_size_mb=1024))

    results = doctor.run_checks(
        cfg=cfg,
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    disk = next(r for r in results if r.name == "store-disk")
    assert disk.status == "FAIL"


def test_config_error_short_circuits(tmp_path: Path) -> None:
    results = doctor.run_checks(config_error="unknown key store.bogus")

    assert len(results) == 1
    assert results[0].name == "config"
    assert results[0].status == "FAIL"
    assert results[0].hint is not None


def test_json_payload_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "is_daemon_alive", lambda *a, **k: True)
    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
        executable=sys.executable,
    )

    payload = doctor.to_json(results)

    assert set(payload) == {"ok", "checks"}
    assert isinstance(payload["ok"], bool)
    for check in payload["checks"]:
        assert set(check) == {"name", "status", "detail", "hint"}
        assert check["status"] in {"PASS", "WARN", "FAIL"}


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_doctor_cli_prints_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentwatch.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(doctor, "is_daemon_alive", lambda *a, **k: False)

    rc = main(["doctor"])

    out = capsys.readouterr().out
    assert "config" in out
    assert "daemon" in out
    assert rc == 1  # daemon down is a FAIL


def test_doctor_cli_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentwatch.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)

    rc = main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert "checks" in payload
    assert rc in (0, 1)
