"""Managed-policy install + honest ``doctor`` tests (M29 DEP-1, #441; PRD 50).

Claude Code managed settings can block user/project hooks
(``allowManagedHooksOnly``, ``strictPluginOnlyCustomization``). agentwatch
installs into user/project settings, so under those controls the recorder is
silently inert. These tests pin the **honest** claim: ``doctor`` reports
``hooks effective: yes | blocked by managed policy | unknown`` and never says
"installed" when the effective policy blocks the recorder. Detection only —
never circumvention.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
from agentwatch.install import HookCommand, InstallError, resolve_scope
from agentwatch.managed_policy import (
    HOOKS_EFFECTIVE_BLOCKED,
    HOOKS_EFFECTIVE_UNKNOWN,
    HOOKS_EFFECTIVE_YES,
    detect_managed_policy,
    managed_install_artifacts,
    managed_settings_paths,
)


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


def _write_hooks(settings: Path, command: str = "/opt/aw/bin/agentwatch-hook") -> None:
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": command, "args": ["pre"]}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def _managed(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "managed-settings.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_managed_settings_paths_per_platform() -> None:
    assert managed_settings_paths("darwin", {}) == (
        Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    )
    assert managed_settings_paths("linux", {}) == (
        Path("/etc/claude-code/managed-settings.json"),
    )
    windows = managed_settings_paths("win32", {"ProgramData": r"C:\ProgramData"})
    assert windows == (Path(r"C:\ProgramData") / "ClaudeCode" / "managed-settings.json",)


def test_managed_settings_env_override() -> None:
    paths = managed_settings_paths("darwin", {"AGENTWATCH_MANAGED_SETTINGS": "/a/x.json:/b/y.json"})
    assert paths == (Path("/a/x.json"), Path("/b/y.json"))


# ---------------------------------------------------------------------------
# Detection truth table
# ---------------------------------------------------------------------------


def test_no_managed_settings_is_not_present() -> None:
    policy = detect_managed_policy([Path("/definitely/absent.json")])

    assert policy.present is False
    assert policy.blocks_user_hooks is False
    assert policy.hooks_effective == HOOKS_EFFECTIVE_YES


def test_allow_managed_hooks_only_blocks(tmp_path: Path) -> None:
    policy = detect_managed_policy([_managed(tmp_path, {"allowManagedHooksOnly": True})])

    assert policy.present is True
    assert policy.managed_hooks_only is True
    assert policy.blocks_user_hooks is True
    assert policy.hooks_effective == HOOKS_EFFECTIVE_BLOCKED
    assert "allowManagedHooksOnly" in policy.reason


def test_strict_plugin_only_blocks(tmp_path: Path) -> None:
    path = _managed(tmp_path, {"strictPluginOnlyCustomization": True})

    policy = detect_managed_policy([path])

    assert policy.blocks_user_hooks is True
    assert policy.hooks_effective == HOOKS_EFFECTIVE_BLOCKED
    assert "strictPluginOnlyCustomization" in policy.reason


def test_managed_agentwatch_hook_is_effective(tmp_path: Path) -> None:
    # A managed hook entry carrying agentwatch is effective even when user hooks are blocked.
    payload = {
        "allowManagedHooksOnly": True,
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
        },
    }
    policy = detect_managed_policy([_managed(tmp_path, payload)])

    assert policy.managed_agentwatch is True
    assert policy.hooks_effective == HOOKS_EFFECTIVE_YES


def test_force_enabled_agentwatch_plugin_is_effective(tmp_path: Path) -> None:
    payload = {
        "allowManagedHooksOnly": True,
        "enabledPlugins": {"agentwatch@org": True, "other@org": False},
    }

    policy = detect_managed_policy([_managed(tmp_path, payload)])

    assert "agentwatch@org" in policy.force_enabled_plugins
    assert policy.managed_agentwatch is True
    assert policy.hooks_effective == HOOKS_EFFECTIVE_YES


def test_unparseable_managed_settings_is_unknown(tmp_path: Path) -> None:
    policy = detect_managed_policy([_managed(tmp_path, "{not json")])

    assert policy.present is True
    assert policy.error is not None
    assert policy.hooks_effective == HOOKS_EFFECTIVE_UNKNOWN


def test_nonblocking_managed_settings_allow_user_hooks(tmp_path: Path) -> None:
    policy = detect_managed_policy([_managed(tmp_path, {"allowManagedHooksOnly": False})])

    assert policy.present is True
    assert policy.blocks_user_hooks is False
    assert policy.hooks_effective == HOOKS_EFFECTIVE_YES


# ---------------------------------------------------------------------------
# doctor: honest claim
# ---------------------------------------------------------------------------


def _run(settings: Path, managed: Path | None, tmp_path: Path) -> dict[str, doctor.CheckResult]:
    results = doctor.run_checks(
        cfg=_cfg(),
        store_path=tmp_path / "records.jsonl",
        socket_path=tmp_path / "d.sock",
        settings_paths={"project": settings, "user": tmp_path / "none.json"},
        managed_paths=[managed] if managed is not None else [],
        executable=sys.executable,
    )
    return {result.name: result for result in results}


def test_doctor_blocked_never_says_installed(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    _write_hooks(settings)
    managed = _managed(tmp_path, {"allowManagedHooksOnly": True})

    hooks = _run(settings, managed, tmp_path)["hooks"]

    assert hooks.status == doctor.WARN
    assert "hooks effective: blocked by managed policy" in hooks.detail
    assert "installed" not in hooks.detail.lower()
    assert hooks.hint is not None


def test_doctor_managed_hook_is_effective(tmp_path: Path) -> None:
    settings = tmp_path / "none.json"
    managed = _managed(
        tmp_path,
        {
            "allowManagedHooksOnly": True,
            "enabledPlugins": {"agentwatch@org": True},
        },
    )

    hooks = _run(settings, managed, tmp_path)["hooks"]

    assert hooks.status == doctor.PASS
    assert "hooks effective: yes" in hooks.detail


def test_doctor_unreadable_policy_is_unknown(tmp_path: Path) -> None:
    managed = _managed(tmp_path, "{not json")

    hooks = _run(tmp_path / "none.json", managed, tmp_path)["hooks"]

    assert hooks.status == doctor.WARN
    assert "hooks effective: unknown" in hooks.detail
    assert "installed" not in hooks.detail.lower()


def test_doctor_no_policy_installed_is_effective(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    _write_hooks(settings)

    hooks = _run(settings, None, tmp_path)["hooks"]

    assert hooks.status == doctor.PASS
    assert "hooks effective: yes" in hooks.detail


# ---------------------------------------------------------------------------
# Install artifacts + uninstall posture
# ---------------------------------------------------------------------------


def test_managed_install_artifacts_cover_hooks_plugin_and_mdm() -> None:
    command = HookCommand(command="/opt/aw/bin/agentwatch-hook", args_prefix=())

    artifacts = managed_install_artifacts(command)

    managed_hooks = artifacts.managed_settings["hooks"]
    assert "PreToolUse" in managed_hooks
    assert artifacts.plugin_manifest["name"] == "agentwatch"
    assert artifacts.mdm_payload["managed-settings.json"]["hooks"]["PreToolUse"]
    # The artifacts are inert data: no function/exec/secret fields.
    rendered = json.dumps(artifacts.to_dict()).lower()
    assert "secret" not in rendered
    assert "token" not in rendered


def test_resolve_scope_rejects_managed() -> None:
    try:
        resolve_scope("managed")
    except InstallError as exc:
        assert "managed" in str(exc)
    else:  # pragma: no cover - the guard must raise
        raise AssertionError("resolve_scope must reject the managed scope")
