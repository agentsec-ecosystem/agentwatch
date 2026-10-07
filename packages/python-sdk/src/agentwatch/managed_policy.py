"""Managed-policy detection for Claude Code installs (M29 DEP-1, #441; PRD 50).

Claude Code managed settings can block user/project hooks
(``allowManagedHooksOnly``, ``strictPluginOnlyCustomization``). agentwatch
installs into project ``settings.local.json`` / user ``settings.json``
(``design/claude-code-hook-contract.md``), so under those controls the recorder
is **silently inert** exactly where regulated buyers deploy.

This module reads the effective managed settings and states the truth per
harness: ``hooks effective: yes | blocked by managed policy | unknown``. It
**detects, never circumvents** — whether to allow the managed install is the
org's decision. It also generates the inert managed-install artifacts (managed
hook settings, org-plugin manifest, MDM payload) that an admin applies through
their own mechanism.

The exact managed key behaviour varies by Claude Code version; verify against a
real managed configuration before GA (ADR-0028).
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.install import EVENT_PHASES, HookCommand, _is_agentwatch_handler

HOOKS_EFFECTIVE_YES = "yes"
HOOKS_EFFECTIVE_BLOCKED = "blocked by managed policy"
HOOKS_EFFECTIVE_UNKNOWN = "unknown"

MANAGED_SETTINGS_ENV = "AGENTWATCH_MANAGED_SETTINGS"

# Managed settings locations per the Claude Code settings reference (2026).
_MACOS_MANAGED = Path("/Library/Application Support/ClaudeCode/managed-settings.json")
_LINUX_MANAGED = Path("/etc/claude-code/managed-settings.json")


def managed_settings_paths(
    platform: str | None = None, env: Mapping[str, str] | None = None
) -> tuple[Path, ...]:
    """Resolve the managed-settings file(s) for the platform.

    ``AGENTWATCH_MANAGED_SETTINGS`` overrides with an ``os.pathsep``-separated
    list (tests / non-standard MDM layouts).
    """
    resolved_env = os.environ if env is None else env
    override = resolved_env.get(MANAGED_SETTINGS_ENV)
    if override:
        return tuple(Path(part) for part in override.split(os.pathsep) if part)
    resolved_platform = sys.platform if platform is None else platform
    if resolved_platform == "darwin":
        return (_MACOS_MANAGED,)
    if resolved_platform.startswith("win"):
        program_data = resolved_env.get("ProgramData", r"C:\ProgramData")
        return (Path(program_data) / "ClaudeCode" / "managed-settings.json",)
    return (_LINUX_MANAGED,)


def _force_enabled_plugins(document: Mapping[str, Any]) -> tuple[str, ...]:
    """Names of force-enabled plugins (``enabledPlugins`` map or list)."""
    enabled = document.get("enabledPlugins")
    if isinstance(enabled, Mapping):
        return tuple(
            sorted(str(name) for name, value in enabled.items() if value is True)
        )
    if isinstance(enabled, list):
        return tuple(sorted(str(name) for name in enabled))
    return ()


def _managed_has_agentwatch(document: Mapping[str, Any]) -> bool:
    hooks = document.get("hooks")
    if isinstance(hooks, Mapping):
        for groups in hooks.values():
            if not isinstance(groups, list):
                continue
            for group in groups:
                if not isinstance(group, Mapping):
                    continue
                handlers = group.get("hooks")
                if isinstance(handlers, list) and any(
                    _is_agentwatch_handler(handler) for handler in handlers
                ):
                    return True
    return any("agentwatch" in name for name in _force_enabled_plugins(document))


@dataclass(frozen=True)
class ManagedPolicy:
    """The effective managed policy that governs whether agentwatch hooks run."""

    present: bool = False
    path: Path | None = None
    managed_hooks_only: bool = False
    strict_plugin_only: bool = False
    managed_agentwatch: bool = False
    force_enabled_plugins: tuple[str, ...] = ()
    error: str | None = None
    blocking_flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocks_user_hooks(self) -> bool:
        """Whether the effective policy stops user/project hooks from running."""
        return self.managed_hooks_only or self.strict_plugin_only

    @property
    def reason(self) -> str:
        if self.blocking_flags:
            return ", ".join(self.blocking_flags)
        return "managed settings"

    @property
    def hooks_effective(self) -> str:
        """``yes`` | ``blocked by managed policy`` | ``unknown`` (never "installed")."""
        if self.error is not None:
            return HOOKS_EFFECTIVE_UNKNOWN
        if self.blocks_user_hooks:
            return HOOKS_EFFECTIVE_YES if self.managed_agentwatch else HOOKS_EFFECTIVE_BLOCKED
        return HOOKS_EFFECTIVE_YES


def _parse_policy(path: Path) -> ManagedPolicy:
    try:
        raw = path.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return ManagedPolicy(present=True, path=path, error=str(exc))
    if not isinstance(document, Mapping):
        return ManagedPolicy(
            present=True, path=path, error="managed settings must be a JSON object"
        )

    flags: list[str] = []
    if document.get("allowManagedHooksOnly") is True:
        flags.append("allowManagedHooksOnly")
    if document.get("strictPluginOnlyCustomization") is True:
        flags.append("strictPluginOnlyCustomization")
    return ManagedPolicy(
        present=True,
        path=path,
        managed_hooks_only=document.get("allowManagedHooksOnly") is True,
        strict_plugin_only=document.get("strictPluginOnlyCustomization") is True,
        managed_agentwatch=_managed_has_agentwatch(document),
        force_enabled_plugins=_force_enabled_plugins(document),
        blocking_flags=tuple(flags),
    )


def detect_managed_policy(paths: Sequence[Path] | None = None) -> ManagedPolicy:
    """Detect the effective managed policy (managed > user > project precedence).

    Only the managed layer is read here; the caller combines it with what is
    installed in the user/project scopes. An unreadable managed file is reported
    ``unknown`` — never assumed permissive.
    """
    resolved = tuple(paths) if paths is not None else managed_settings_paths()
    present = [Path(path) for path in resolved if Path(path).is_file()]
    if not present:
        return ManagedPolicy()

    policies = [_parse_policy(path) for path in present]
    error = next((policy.error for policy in policies if policy.error is not None), None)
    return ManagedPolicy(
        present=True,
        path=policies[0].path,
        managed_hooks_only=any(policy.managed_hooks_only for policy in policies),
        strict_plugin_only=any(policy.strict_plugin_only for policy in policies),
        managed_agentwatch=any(policy.managed_agentwatch for policy in policies),
        force_enabled_plugins=tuple(
            sorted({name for policy in policies for name in policy.force_enabled_plugins})
        ),
        error=error,
        blocking_flags=tuple(
            sorted({flag for policy in policies for flag in policy.blocking_flags})
        ),
    )


def install_guidance(policy: ManagedPolicy) -> str | None:
    """A one-line, non-alarming explanation of what the policy means for ``init``."""
    if policy.error is not None:
        return (
            f"managed settings at {policy.path} could not be read; recorder "
            "effectiveness is unknown"
        )
    if policy.blocks_user_hooks and not policy.managed_agentwatch:
        return (
            f"managed policy blocks user/project hooks ({policy.reason}); a "
            "user/project install will be inert. Deploy agentwatch as a managed "
            "hook or force-enabled org plugin "
            "(docs/design/managed-policy-install.md)"
        )
    return None


# ---------------------------------------------------------------------------
# Managed-install artifacts (inert data an admin applies)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManagedInstallArtifacts:
    """The managed hook / org-plugin / MDM artifacts (never applied by us)."""

    managed_settings: dict[str, Any]
    plugin_manifest: dict[str, Any]
    mdm_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "managed-settings.json": self.managed_settings,
            "plugin.json": self.plugin_manifest,
            "mdm-payload.json": self.mdm_payload,
        }


def _hook_blocks(command: HookCommand, *, async_hooks: bool = True) -> dict[str, Any]:
    return {
        event: [{"matcher": "*", "hooks": [command.handler(phase, async_hooks=async_hooks)]}]
        for event, phase in EVENT_PHASES.items()
    }


def managed_install_artifacts(command: HookCommand) -> ManagedInstallArtifacts:
    """Build the inert managed hook / org-plugin / MDM install artifacts."""
    hooks = _hook_blocks(command)
    managed_settings: dict[str, Any] = {"hooks": hooks}
    plugin_manifest: dict[str, Any] = {
        "name": "agentwatch",
        "description": "Local, tamper-evident agent activity recording",
        "hooks": hooks,
    }
    return ManagedInstallArtifacts(
        managed_settings=managed_settings,
        plugin_manifest=plugin_manifest,
        mdm_payload={"managed-settings.json": {"hooks": hooks}},
    )


__all__ = [
    "HOOKS_EFFECTIVE_BLOCKED",
    "HOOKS_EFFECTIVE_UNKNOWN",
    "HOOKS_EFFECTIVE_YES",
    "MANAGED_SETTINGS_ENV",
    "ManagedInstallArtifacts",
    "ManagedPolicy",
    "detect_managed_policy",
    "install_guidance",
    "managed_install_artifacts",
    "managed_settings_paths",
]
