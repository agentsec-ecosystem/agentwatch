"""``agentwatch doctor``: ordered preflight/fix checklist (M5 C1, #175).

NFR-4 promises a first-run <=15 min, but failures are silent: hooks missing,
daemon dead, socket moved, config invalid. Doctor runs the checks the runbook
otherwise leaves to the operator, each with a one-line fix hint, and exits
non-zero only when a check **fails** (warnings are advisory).

It composes existing primitives (configuration, install, store, selftest); it
reads local paths only and never prints secrets from config.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch.configuration import AgentwatchConfig
from agentwatch.harness_drift import harness_drift_observations
from agentwatch.hook import default_socket_path
from agentwatch.install import (
    HookCommand,
    hooks_installed,
    is_daemon_alive,
    resolve_hook_command,
    resolve_scope,
)
from agentwatch.managed_policy import (
    HOOKS_EFFECTIVE_BLOCKED,
    HOOKS_EFFECTIVE_UNKNOWN,
    HOOKS_EFFECTIVE_YES,
    ManagedPolicy,
    detect_managed_policy,
)
from agentwatch.redact import redaction_config_from_mode
from agentwatch.selftest import run_redaction_self_test
from agentwatch.signing import signing_status
from agentwatch.store import RecordStore

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

# Ordered checklist: (check name, short description). Stable order is contract.
CHECKS: tuple[tuple[str, str], ...] = (
    ("config", "configuration loads and resolves"),
    ("hooks", "hooks installed in exactly one scope"),
    ("daemon", "daemon alive and the socket accepts a probe"),
    ("hook-entrypoint", "hook entry point resolves and is executable"),
    ("store-chain", "store hash chain verifies"),
    ("redaction-self-test", "redaction self-test passes"),
    ("store-disk", "store path writable and free disk >= max_size_mb"),
    ("retention", "retention window is sane (>= 1 day)"),
    ("harness-drift", "no unrecognized harness fields observed"),
    ("signing", "signing key posture and availability"),
    ("distribution", "agentwatch provided by the expected distribution"),
    ("version", "version self-report"),
)


@dataclass(frozen=True)
class CheckResult:
    """One doctor check: status plus an actionable hint on non-PASS."""

    name: str
    status: str
    detail: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "hint": self.hint,
        }


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always present on 3.10+
        return "0.1.0"
    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.1.0"


def _check_config(cfg: AgentwatchConfig | None, config_error: str | None) -> CheckResult:
    if config_error is not None:
        return CheckResult(
            "config",
            FAIL,
            f"configuration error: {config_error}",
            "fix the config file or remove the offending --set override",
        )
    assert cfg is not None
    return CheckResult(
        "config",
        PASS,
        f"harness={cfg.harness} mode={cfg.mode} privacy.mode={cfg.privacy.mode}",
    )


def _check_distribution() -> CheckResult:
    """Warn when the ``agentwatch`` module came from a namesake distribution (NAM-1)."""
    from agentwatch import naming

    warning = naming.distribution_warning()
    if warning is None:
        return CheckResult("distribution", PASS, naming.DISTRIBUTION_NAME)
    return CheckResult("distribution", WARN, warning, f"reinstall with `{naming.FULL_INSTALL}`")


def _check_hooks(
    settings_paths: Mapping[str, Path], policy: ManagedPolicy | None = None
) -> CheckResult:
    effective = policy or ManagedPolicy()
    installed = [scope for scope, path in settings_paths.items() if hooks_installed(Path(path))]

    # DEP-1: never claim "installed" when the effective policy blocks the recorder.
    if effective.error is not None:
        return CheckResult(
            "hooks",
            WARN,
            f"hooks effective: {HOOKS_EFFECTIVE_UNKNOWN} (managed settings unreadable)",
            "fix or remove the managed settings file, or point "
            "AGENTWATCH_MANAGED_SETTINGS at the right path",
        )
    if effective.blocks_user_hooks:
        if effective.managed_agentwatch:
            return CheckResult(
                "hooks",
                PASS,
                f"hooks effective: {HOOKS_EFFECTIVE_YES} (managed hook/plugin)",
            )
        return CheckResult(
            "hooks",
            WARN,
            f"hooks effective: {HOOKS_EFFECTIVE_BLOCKED} ({effective.reason})",
            "deploy agentwatch as a managed hook or force-enabled org plugin "
            "(docs/design/managed-policy-install.md)",
        )

    if len(installed) == 1:
        return CheckResult(
            "hooks", PASS, f"hooks effective: {HOOKS_EFFECTIVE_YES} (installed: {installed[0]})"
        )
    if not installed:
        return CheckResult(
            "hooks",
            WARN,
            "hooks effective: no (not installed in any scope)",
            "run `agentwatch init` to install hooks",
        )
    return CheckResult(
        "hooks",
        WARN,
        f"hooks effective: {HOOKS_EFFECTIVE_YES} but installed in both scopes "
        f"({', '.join(sorted(installed))})",
        "remove one scope to avoid double-recording",
    )


def _check_daemon(socket_path: Path | str) -> CheckResult:
    if is_daemon_alive(socket_path):
        return CheckResult("daemon", PASS, "alive; socket probe accepted")
    return CheckResult(
        "daemon",
        FAIL,
        "not reachable on the daemon socket",
        "run `agentwatch init` (or start the daemon) and retry",
    )


def _entrypoint_executable(command: HookCommand) -> bool:
    if command.args_prefix:  # interpreter -m agentwatch.hook
        return os.access(command.command, os.X_OK)
    if Path(command.command).is_absolute() or os.sep in command.command:
        return os.access(command.command, os.X_OK)
    resolved = shutil.which(command.command)
    return resolved is not None and os.access(resolved, os.X_OK)


def _check_hook_entrypoint(executable: str | None) -> CheckResult:
    command = resolve_hook_command(executable)
    if _entrypoint_executable(command):
        rendered = " ".join([command.command, *command.args_prefix])
        return CheckResult("hook-entrypoint", PASS, rendered)
    return CheckResult(
        "hook-entrypoint",
        FAIL,
        f"not executable: {command.command}",
        "reinstall agentwatch so the `agentwatch-hook` entry point resolves",
    )


def _existing_ancestor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _check_store_chain(store_path: Path) -> CheckResult:
    if not store_path.exists() or store_path.stat().st_size == 0:
        return CheckResult("store-chain", PASS, "no records yet")
    status = RecordStore(store_path).verify()
    if status.ok:
        return CheckResult("store-chain", PASS, f"chain ok ({status.checked} entries)")
    return CheckResult(
        "store-chain",
        FAIL,
        f"chain broken at seq {status.broken_at}",
        "preserve evidence; see docs/runbooks/tamper-response.md",
    )


def _check_redaction(cfg: AgentwatchConfig) -> CheckResult:
    result = run_redaction_self_test(redaction_config_from_mode(cfg.privacy.mode))
    if result.passed:
        return CheckResult("redaction-self-test", PASS, f"corpus passed ({result.checked} items)")
    return CheckResult(
        "redaction-self-test",
        FAIL,
        f"corpus leaked in {len(result.leaks)} category(ies); export stays blocked",
        "restore the default redaction config and re-run the self-test",
    )


def _check_store_disk(cfg: AgentwatchConfig, store: Path) -> CheckResult:
    base = _existing_ancestor(store.parent)
    if not os.access(base, os.W_OK):
        return CheckResult(
            "store-disk",
            FAIL,
            f"not writable: {base}",
            "fix permissions or point store.path elsewhere",
        )
    free_mb = shutil.disk_usage(base).free / (1024 * 1024)
    if free_mb < cfg.store.max_size_mb:
        return CheckResult(
            "store-disk",
            FAIL,
            f"free {free_mb:.0f} MB < store.max_size_mb {cfg.store.max_size_mb} MB",
            "free disk space or lower store.max_size_mb",
        )
    return CheckResult(
        "store-disk",
        PASS,
        f"writable; free {free_mb:.0f} MB >= {cfg.store.max_size_mb} MB",
    )


def _check_retention(cfg: AgentwatchConfig, store_path: Path | None = None) -> CheckResult:
    if cfg.store.retention_days < 1:
        return CheckResult(
            "retention",
            FAIL,
            f"retention_days={cfg.store.retention_days}",
            "set store.retention_days to at least 1",
        )
    overdue = _overdue_records(store_path, cfg.store.retention_days)
    if overdue:
        return CheckResult(
            "retention",
            WARN,
            f"{overdue} record(s) older than the {cfg.store.retention_days} day window",
            "run `agentwatch retention apply` (or pick a profile)",
        )
    return CheckResult("retention", PASS, f"{cfg.store.retention_days} day(s)")


def _overdue_records(store_path: Path | None, retention_days: int) -> int:
    """Records past the retention window — a visible sign the run was missed."""
    if store_path is None or not Path(store_path).exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    try:
        records = RecordStore(Path(store_path)).records()
    except (OSError, ValueError):  # pragma: no cover - unreadable store
        return 0
    return sum(1 for record in records if record.started_at < cutoff)


def _check_harness_drift(store_path: Path) -> CheckResult:
    if not store_path.exists() or store_path.stat().st_size == 0:
        return CheckResult("harness-drift", PASS, "no drift observed")
    observations = harness_drift_observations(RecordStore(store_path))
    if not observations:
        return CheckResult("harness-drift", PASS, "no drift observed")
    newest = observations[-1]
    named = ", ".join(newest.fields) if newest.fields else (newest.phase or "")
    return CheckResult(
        "harness-drift",
        WARN,
        f"{len(observations)} observation(s); newest: {named}",
        "review unrecognized harness fields; additive fields are normal",
    )


def _check_signing(store_path: Path) -> CheckResult:
    store = RecordStore(store_path) if store_path.exists() else None
    status = signing_status(store, store_path.parent)
    if status.key_id is None:
        return CheckResult(
            "signing",
            PASS,
            "not configured (optional; `checkpoint export --sign`)",
        )
    if status.key_present:
        return CheckResult("signing", PASS, f"{status.key_id} (epoch {status.epoch})")
    return CheckResult(
        "signing",
        WARN,
        status.summary,
        "restore the key or start a new epoch with `checkpoint rotate`",
    )


def run_checks(
    cfg: AgentwatchConfig | None = None,
    *,
    config_error: str | None = None,
    store_path: Path | str | None = None,
    socket_path: Path | str | None = None,
    settings_paths: Mapping[str, Path] | None = None,
    managed_paths: Sequence[Path] | None = None,
    executable: str | None = None,
) -> list[CheckResult]:
    """Run the ordered checklist and return every result.

    Args:
        cfg: the loaded operator configuration; ``None`` only when loading
            failed (pass ``config_error``).
        config_error: message from a failed config load; short-circuits to a
            single failing ``config`` check.
        store_path: override the records JSONL path (tests).
        socket_path: override the daemon socket path (tests).
        settings_paths: override ``{"project": Path, "user": Path}`` (tests).
        managed_paths: override the managed-settings locations (tests); the
            platform locations are used when ``None``.
        executable: interpreter used to resolve the hook entry point (tests).
    """
    if cfg is None or config_error is not None:
        return [_check_config(cfg, config_error or "configuration could not be loaded")]

    resolved_store = (
        Path(store_path)
        if store_path is not None
        else Path(cfg.store.path).expanduser() / "records.jsonl"
    )
    resolved_socket = socket_path if socket_path is not None else default_socket_path()
    resolved_settings: Mapping[str, Path] = settings_paths or {
        "project": resolve_scope("project").settings_path,
        "user": resolve_scope("user").settings_path,
    }
    policy = detect_managed_policy(managed_paths)

    return [
        _check_config(cfg, None),
        _check_hooks(resolved_settings, policy),
        _check_daemon(resolved_socket),
        _check_hook_entrypoint(executable),
        _check_store_chain(resolved_store),
        _check_redaction(cfg),
        _check_store_disk(cfg, resolved_store),
        _check_retention(cfg, resolved_store),
        _check_harness_drift(resolved_store),
        _check_signing(resolved_store),
        _check_distribution(),
        CheckResult("version", PASS, _version()),
    ]


def all_passed(results: Sequence[CheckResult]) -> bool:
    """Whether every check avoided a FAIL (warnings do not fail the run)."""
    return all(result.status != FAIL for result in results)


def to_json(results: Sequence[CheckResult], *, ok: bool | None = None) -> dict[str, Any]:
    """The machine-readable doctor payload for scripts/CI."""
    return {
        "ok": all_passed(results) if ok is None else ok,
        "checks": [result.to_dict() for result in results],
    }
