"""Consent-first A2A proxy install (M29 A2A-1 #364, PRD 45, ADR-0025).

Install re-points an A2A client's ``a2aAgents`` entries at the local
interposition proxy and records the exact original bytes plus a manifest so
``uninstall`` restores the file **identically**. Fail closed: an unparseable
config is refused and a file that changed after install is left untouched.

Two scopes mirror the hook and MCP install scopes: ``project`` → ``<cwd>/.a2a.json``
and ``user`` → ``~/.a2a.json``. (This is agentwatch's interposition convention;
A2A defines no standard client config file.)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.install import InstallError

CONFIG_KEY = "a2aAgents"
_BACKUP_SUFFIX = ".agentwatch-a2a-backup"
_MANIFEST_SUFFIX = ".agentwatch-a2a-manifest.json"
_MANIFEST_VERSION = 1


class A2aConfigError(InstallError):
    """Raised when an A2A config cannot be read, installed, or restored safely."""


@dataclass(frozen=True)
class A2aProxyCommand:
    """The executable + argv prefix that launches the stdio proxy."""

    command: str
    args_prefix: tuple[str, ...] = ()

    def args_for(
        self, agent: str, original_command: str, original_args: Sequence[str]
    ) -> list[str]:
        """Return the proxy argv suffix that spawns ``original_command``."""
        return [
            *self.args_prefix,
            "--agent",
            agent,
            "--",
            original_command,
            *original_args,
        ]


def resolve_a2a_proxy_command(executable: str | None = None) -> A2aProxyCommand:
    """Resolve how a client should invoke the stdio A2A proxy.

    Prefers the ``agentwatch-a2a-proxy`` entry point next to the running
    interpreter, then any on PATH, then ``python -m agentwatch.a2a_proxy``.
    """
    interpreter = executable or sys.executable
    sibling = Path(interpreter).with_name("agentwatch-a2a-proxy")
    if sibling.exists():
        return A2aProxyCommand(command=str(sibling))
    found = shutil.which("agentwatch-a2a-proxy")
    if found:
        return A2aProxyCommand(command=found)
    return A2aProxyCommand(command=interpreter, args_prefix=("-m", "agentwatch.a2a_proxy"))


@dataclass(frozen=True)
class A2aConfigTarget:
    scope: str
    path: Path


def resolve_a2a_scope(
    scope: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> A2aConfigTarget:
    """Resolve the A2A config file for ``project`` (default) or ``user`` scope."""
    if scope == "project":
        base = cwd or Path.cwd()
        return A2aConfigTarget(scope="project", path=base / ".a2a.json")
    if scope == "user":
        base = home or Path.home()
        return A2aConfigTarget(scope="user", path=base / ".a2a.json")
    raise A2aConfigError(f"unknown scope {scope!r}; expected 'project' or 'user'")


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + _BACKUP_SUFFIX)


def _manifest_path(path: Path) -> Path:
    return path.with_name(path.name + _MANIFEST_SUFFIX)


@dataclass
class A2aInstallReport:
    target: A2aConfigTarget
    created: bool
    repointed: tuple[str, ...]
    skipped: tuple[str, ...] = ()
    backup_path: Path | None = None
    manifest_path: Path | None = None


@dataclass
class A2aUninstallReport:
    restored: bool
    deleted: bool
    repointed_removed: tuple[str, ...] = ()
    reason: str | None = None


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise A2aConfigError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise A2aConfigError(f"{path} must contain a JSON object")
    return data


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def install_a2a_proxy(
    target: A2aConfigTarget,
    *,
    proxy_command: A2aProxyCommand,
    agents: Sequence[str] | None = None,
) -> A2aInstallReport:
    """Re-point the selected A2A agents at the local proxy (consent-first).

    Only agents present at install time are touched. Unrelated keys are
    preserved. A stdio agent's ``command``/``args`` are wrapped so the client
    launches the proxy, which spawns the real agent. The exact original bytes
    are backed up and a manifest records what was written.
    """
    path = target.path
    created = not path.exists()
    original_bytes = path.read_bytes() if not created else b""

    data = _load(path)
    agents_obj = data.get(CONFIG_KEY)
    if agents_obj is None:
        agents_obj = {}
        data[CONFIG_KEY] = agents_obj
    if not isinstance(agents_obj, dict):
        raise A2aConfigError(f"{path}: {CONFIG_KEY!r} must be a JSON object")

    if agents is None:
        selected = list(agents_obj)
        skipped: tuple[str, ...] = ()
    else:
        selected = [name for name in agents if name in agents_obj]
        skipped = tuple(name for name in agents if name not in agents_obj)

    originals: dict[str, Any] = {}
    repointed: list[str] = []
    for name in selected:
        entry = agents_obj.get(name)
        if not isinstance(entry, dict):
            continue
        if not isinstance(entry.get("command"), str):
            continue
        args = [str(arg) for arg in entry.get("args") or []]
        new_entry = {
            **entry,
            "command": proxy_command.command,
            "args": proxy_command.args_for(name, entry["command"], args),
        }
        originals[name] = entry
        agents_obj[name] = new_entry
        repointed.append(name)

    written_bytes = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    _write_bytes(_backup_path(path), original_bytes)
    manifest = {
        "version": _MANIFEST_VERSION,
        "scope": target.scope,
        "created": created,
        "written_sha256": hashlib.sha256(written_bytes).hexdigest(),
        "proxy_command": proxy_command.command,
        "repointed": list(repointed),
        "agents": originals,
    }
    _write_bytes(_manifest_path(path), (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    _write_bytes(path, written_bytes)

    return A2aInstallReport(
        target=target,
        created=created,
        repointed=tuple(repointed),
        skipped=skipped,
        backup_path=_backup_path(path),
        manifest_path=_manifest_path(path),
    )


def _load_manifest(target: A2aConfigTarget) -> dict[str, Any]:
    path = _manifest_path(target.path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _cleanup(path: Path) -> None:
    _manifest_path(path).unlink(missing_ok=True)
    _backup_path(path).unlink(missing_ok=True)


def uninstall_a2a_proxy(target: A2aConfigTarget) -> A2aUninstallReport:
    """Restore the config from the backup, deleting a file we created.

    Fails closed: if the current file no longer matches what install wrote, the
    file is left untouched and a reason is reported. Agents added after install
    are untouched because only the backup bytes are restored.
    """
    manifest = _load_manifest(target)
    if not manifest:
        return A2aUninstallReport(restored=False, deleted=False, reason="not installed")

    repointed = tuple(manifest.get("repointed") or ())
    path = target.path
    if not path.exists():
        _cleanup(path)
        return A2aUninstallReport(
            restored=False,
            deleted=False,
            repointed_removed=repointed,
            reason="config file is missing",
        )

    current = path.read_bytes()
    if hashlib.sha256(current).hexdigest() != manifest.get("written_sha256"):
        return A2aUninstallReport(
            restored=False,
            deleted=False,
            reason="config changed since install; leaving it untouched",
        )

    if manifest.get("created"):
        path.unlink(missing_ok=True)
        _cleanup(path)
        return A2aUninstallReport(restored=False, deleted=True, repointed_removed=repointed)

    backup = _backup_path(path)
    if not backup.exists():
        return A2aUninstallReport(
            restored=False, deleted=False, reason="backup missing; leaving config untouched"
        )
    path.write_bytes(backup.read_bytes())
    _cleanup(path)
    return A2aUninstallReport(restored=True, deleted=False, repointed_removed=repointed)


def a2a_proxy_installed(target: A2aConfigTarget) -> bool:
    """Whether an agentwatch A2A-proxy manifest is present for this target."""
    return bool(_load_manifest(target))


__all__ = [
    "A2aConfigError",
    "A2aConfigTarget",
    "A2aInstallReport",
    "A2aProxyCommand",
    "A2aUninstallReport",
    "a2a_proxy_installed",
    "install_a2a_proxy",
    "resolve_a2a_proxy_command",
    "resolve_a2a_scope",
    "uninstall_a2a_proxy",
]