"""MCP server config re-pointing for ``agentwatch init --mcp-proxy`` (M10 N1 #212).

Install re-points a harness's ``mcpServers`` at the local interposition proxy and
records a byte-exact backup plus a manifest so ``uninstall`` can restore the file
**identically**. Fail closed: an unparseable config is refused (F7), and a file
that changed after install is left untouched.

Two scopes mirror the hook install scopes (D-M4): ``project`` → ``<cwd>/.mcp.json``
and ``user`` → ``~/.claude.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.install import InstallError

_BACKUP_SUFFIX = ".agentwatch-mcp-backup"
_MANIFEST_SUFFIX = ".agentwatch-mcp-manifest.json"
_MANIFEST_VERSION = 1


class McpConfigError(InstallError):
    """Raised when an MCP config cannot be read, installed, or restored safely."""


# ---------------------------------------------------------------------------
# Proxy command resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class McpProxyCommand:
    """The executable + argv prefix that launches the stdio proxy."""

    command: str
    args_prefix: tuple[str, ...] = ()

    def args_for(
        self, server: str, original_command: str, original_args: Sequence[str]
    ) -> list[str]:
        """Return the proxy argv suffix that spawns ``original_command``."""
        return [
            *self.args_prefix,
            "--server",
            server,
            "--",
            original_command,
            *original_args,
        ]


def resolve_mcp_proxy_command(executable: str | None = None) -> McpProxyCommand:
    """Resolve how a harness should invoke the stdio MCP proxy.

    Prefers the ``agentwatch-mcp-proxy`` entry point next to the running
    interpreter, then any on PATH, then ``python -m agentwatch.mcp_proxy``.
    """
    interpreter = executable or sys.executable
    sibling = Path(interpreter).with_name("agentwatch-mcp-proxy")
    if sibling.exists():
        return McpProxyCommand(command=str(sibling))
    found = shutil.which("agentwatch-mcp-proxy")
    if found:
        return McpProxyCommand(command=found)
    return McpProxyCommand(command=interpreter, args_prefix=("-m", "agentwatch.mcp_proxy"))


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class McpConfigTarget:
    scope: str
    path: Path


def resolve_mcp_scope(
    scope: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> McpConfigTarget:
    """Resolve the MCP config file for ``project`` (default) or ``user`` scope."""
    if scope == "project":
        base = cwd or Path.cwd()
        return McpConfigTarget(scope="project", path=base / ".mcp.json")
    if scope == "user":
        base = home or Path.home()
        return McpConfigTarget(scope="user", path=base / ".claude.json")
    raise McpConfigError(f"unknown scope {scope!r}; expected 'project' or 'user'")


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + _BACKUP_SUFFIX)


def _manifest_path(path: Path) -> Path:
    return path.with_name(path.name + _MANIFEST_SUFFIX)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@dataclass
class McpInstallReport:
    target: McpConfigTarget
    created: bool
    repointed: tuple[str, ...]
    http_routes: dict[str, str] = field(default_factory=dict)
    skipped: tuple[str, ...] = ()
    backup_path: Path | None = None
    manifest_path: Path | None = None
    port: int = 8765


@dataclass
class McpUninstallReport:
    restored: bool
    deleted: bool
    repointed_removed: tuple[str, ...] = ()
    reason: str | None = None


# ---------------------------------------------------------------------------
# Install / restore
# ---------------------------------------------------------------------------


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise McpConfigError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise McpConfigError(f"{path} must contain a JSON object")
    return data


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def install_mcp_proxy(
    target: McpConfigTarget,
    *,
    proxy_command: McpProxyCommand,
    port: int,
    servers: Sequence[str] | None = None,
    http_host: str = "127.0.0.1",
) -> McpInstallReport:
    """Re-point the selected MCP servers at the local proxy (consent-first).

    Only servers present at install time are touched. ``env``/``type`` and any
    unrelated keys are preserved. A stdio server's ``command``/``args`` are
    wrapped so the harness launches the proxy, which spawns the real server; an
    HTTP/SSE server's ``url`` becomes the loopback route. The exact original
    bytes are backed up and a manifest records what was written.
    """
    path = target.path
    created = not path.exists()
    original_bytes = path.read_bytes() if not created else b""

    data = _load(path)
    servers_obj = data.get("mcpServers")
    if servers_obj is None:
        servers_obj = {}
        data["mcpServers"] = servers_obj
    if not isinstance(servers_obj, dict):
        raise McpConfigError(f"{path}: 'mcpServers' must be a JSON object")

    if servers is None:
        selected = list(servers_obj)
        skipped: tuple[str, ...] = ()
    else:
        selected = [name for name in servers if name in servers_obj]
        skipped = tuple(name for name in servers if name not in servers_obj)

    originals: dict[str, Any] = {}
    repointed: list[str] = []
    http_routes: dict[str, str] = {}
    for name in selected:
        entry = servers_obj.get(name)
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("command"), str) and isinstance(entry.get("args", []), list):
            args = [str(arg) for arg in entry.get("args") or []]
            new_entry = {
                **entry,
                "command": proxy_command.command,
                "args": proxy_command.args_for(name, entry["command"], args),
            }
        elif isinstance(entry.get("url"), str) and entry["url"]:
            http_routes[name] = entry["url"]
            new_entry = {**entry, "url": f"http://{http_host}:{port}/{name}"}
        else:
            continue
        originals[name] = entry
        servers_obj[name] = new_entry
        repointed.append(name)

    written_bytes = (json.dumps(data, indent=2) + "\n").encode("utf-8")

    _write_bytes(_backup_path(path), original_bytes)
    manifest = {
        "version": _MANIFEST_VERSION,
        "scope": target.scope,
        "created": created,
        "written_sha256": hashlib.sha256(written_bytes).hexdigest(),
        "port": port,
        "proxy_command": proxy_command.command,
        "repointed": list(repointed),
        "http_routes": http_routes,
        "servers": originals,
    }
    _write_bytes(_manifest_path(path), (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    _write_bytes(path, written_bytes)

    return McpInstallReport(
        target=target,
        created=created,
        repointed=tuple(repointed),
        http_routes=http_routes,
        skipped=skipped,
        backup_path=_backup_path(path),
        manifest_path=_manifest_path(path),
        port=port,
    )


def _load_manifest(target: McpConfigTarget) -> dict[str, Any]:
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


def uninstall_mcp_proxy(target: McpConfigTarget) -> McpUninstallReport:
    """Restore the config from the backup, deleting a file we created.

    Fails closed: if the current file no longer matches what install wrote, the
    file is left untouched and a reason is reported. Servers added after install
    are untouched because only the backup bytes are restored.
    """
    manifest = _load_manifest(target)
    if not manifest:
        return McpUninstallReport(restored=False, deleted=False, reason="not installed")

    repointed = tuple(manifest.get("repointed") or ())
    path = target.path
    if not path.exists():
        _cleanup(path)
        return McpUninstallReport(
            restored=False,
            deleted=False,
            repointed_removed=repointed,
            reason="config file is missing",
        )

    current = path.read_bytes()
    if hashlib.sha256(current).hexdigest() != manifest.get("written_sha256"):
        return McpUninstallReport(
            restored=False,
            deleted=False,
            reason="config changed since install; leaving it untouched",
        )

    if manifest.get("created"):
        path.unlink(missing_ok=True)
        _cleanup(path)
        return McpUninstallReport(restored=False, deleted=True, repointed_removed=repointed)

    backup = _backup_path(path)
    if not backup.exists():
        return McpUninstallReport(
            restored=False, deleted=False, reason="backup missing; leaving config untouched"
        )
    path.write_bytes(backup.read_bytes())
    _cleanup(path)
    return McpUninstallReport(restored=True, deleted=False, repointed_removed=repointed)


def mcp_proxy_installed(target: McpConfigTarget) -> bool:
    """Whether an agentwatch MCP-proxy manifest is present for this target."""
    return bool(_load_manifest(target))
