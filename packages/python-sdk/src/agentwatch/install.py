"""Hook installation and daemon lifecycle for ``agentwatch init`` (M3 #159).

This module owns every filesystem and process side effect of installing
agentwatch into Claude Code: merging hook entries into a Claude Code settings
file, resolving the hook entry point, and starting/stopping the local daemon.
The CLI stays a thin dispatcher over these functions so the side effects are
testable in isolation.

Fail-closed: a malformed settings file is refused, never overwritten (F7).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.hook import default_socket_path

# Claude Code events agentwatch manages, and the hook phase each forwards.
EVENT_PHASES: dict[str, str] = {
    "PreToolUse": "pre",
    "PostToolUse": "post",
    "PostToolUseFailure": "post",
    "PermissionDenied": "denied",
    "Notification": "notification",
    "PreCompact": "compact",
    "UserPromptSubmit": "prompt",
    "SessionStart": "session-start",
    "SessionEnd": "session-end",
}

_DAEMON_START_TIMEOUT_SECONDS = 10.0
_DAEMON_STOP_TIMEOUT_SECONDS = 5.0


class InstallError(RuntimeError):
    """Raised when hook installation cannot proceed safely (fail-closed)."""


# ---------------------------------------------------------------------------
# Hook command resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HookCommand:
    """The executable used by Claude Code hook handlers (exec form)."""

    command: str
    args_prefix: tuple[str, ...] = ()

    def handler(self, phase: str, *, async_hooks: bool = True) -> dict[str, Any]:
        handler: dict[str, Any] = {
            "type": "command",
            "command": self.command,
            "args": [*self.args_prefix, phase],
        }
        if async_hooks:
            handler["async"] = True
        return handler


def resolve_hook_command(executable: str | None = None) -> HookCommand:
    """Resolve how Claude Code should invoke the hook client.

    Prefers the ``agentwatch-hook`` entry point next to the running interpreter
    (so npx/pipx installs work even though they are not on the session PATH),
    then any ``agentwatch-hook`` on PATH, then ``python -m agentwatch.hook``.
    """
    interpreter = executable or sys.executable
    sibling = Path(interpreter).with_name("agentwatch-hook")
    if sibling.exists():
        return HookCommand(command=str(sibling), args_prefix=())
    found = shutil.which("agentwatch-hook")
    if found:
        return HookCommand(command=found, args_prefix=())
    return HookCommand(command=interpreter, args_prefix=("-m", "agentwatch.hook"))


def _is_agentwatch_handler(handler: Any) -> bool:
    """Whether a hook handler was written by agentwatch (any path or version)."""
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    tokens = [handler.get("command"), *(handler.get("args") or [])]
    joined = " ".join(token for token in tokens if isinstance(token, str))
    return "agentwatch-hook" in joined or "agentwatch.hook" in joined


# ---------------------------------------------------------------------------
# Settings file manipulation
# ---------------------------------------------------------------------------


def _load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InstallError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InstallError(f"{path} must contain a JSON object")
    return data


def _write_settings(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _strip_owned(hooks: dict[str, Any]) -> bool:
    """Remove agentwatch handlers from every event; drop groups left empty."""
    removed = False
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups: list[Any] = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                kept_groups.append(group)
                continue
            kept = [h for h in handlers if not _is_agentwatch_handler(h)]
            if len(kept) != len(handlers):
                removed = True
            if kept:
                group = {**group, "hooks": kept}
                kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]
    return removed


def install_hooks(settings_path: Path, command: HookCommand, *, async_hooks: bool = True) -> None:
    """Merge agentwatch hooks into a Claude Code settings file, idempotently."""
    data = _load_settings(settings_path)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError(f"{settings_path}: 'hooks' must be a JSON object")
    _strip_owned(hooks)
    for event, phase in EVENT_PHASES.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):  # pragma: no cover - guarded by _strip_owned
            raise InstallError(f"{settings_path}: 'hooks.{event}' must be a list")
        groups.append({"matcher": "*", "hooks": [command.handler(phase, async_hooks=async_hooks)]})
    _write_settings(settings_path, data)


def uninstall_hooks(settings_path: Path) -> bool:
    """Remove agentwatch hooks, preserving everything else. False if absent."""
    if not settings_path.exists():
        return False
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    removed = _strip_owned(hooks)
    if isinstance(hooks, dict) and not hooks:
        del data["hooks"]
    if removed:
        _write_settings(settings_path, data)
    return removed


def hooks_installed(settings_path: Path) -> bool:
    """Whether the settings file currently carries any agentwatch hook."""
    if not settings_path.exists():
        return False
    try:
        data = _load_settings(settings_path)
    except InstallError:
        return False
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if isinstance(group, dict):
                handlers = group.get("hooks")
                if isinstance(handlers, list) and any(_is_agentwatch_handler(h) for h in handlers):
                    return True
    return False


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HookTarget:
    scope: str
    settings_path: Path


def resolve_scope(
    scope: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> HookTarget:
    """Resolve the settings file for ``project`` (default) or ``user`` scope."""
    if scope == "project":
        base = cwd or Path.cwd()
        return HookTarget(scope="project", settings_path=base / ".claude" / "settings.local.json")
    if scope == "user":
        base = home or Path.home()
        return HookTarget(scope="user", settings_path=base / ".claude" / "settings.json")
    raise InstallError(f"unknown scope {scope!r}; expected 'project' or 'user'")


# ---------------------------------------------------------------------------
# Daemon lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DaemonPaths:
    socket: Path
    pid: Path
    log: Path
    records: Path


def daemon_paths() -> DaemonPaths:
    """Resolve the daemon's socket, pid/log, and JSONL sink from config."""
    from agentwatch.configuration import load_config

    base = Path(load_config().store.path).expanduser()
    return DaemonPaths(
        socket=Path(default_socket_path()),
        pid=base / "daemon.pid",
        log=base / "daemon.log",
        records=base / "records.jsonl",
    )


def is_daemon_alive(socket_path: Path | str | None = None) -> bool:
    """Whether a daemon is accepting connections on the socket."""
    path = Path(socket_path) if socket_path is not None else Path(default_socket_path())
    if not path.exists():
        return False
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.3)
        probe.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _child_env() -> dict[str, str]:
    src = str(Path(__file__).resolve().parents[1])
    existing = os.environ.get("PYTHONPATH", "")
    return {**os.environ, "PYTHONPATH": src + (os.pathsep + existing if existing else "")}


def start_daemon(paths: DaemonPaths | None = None) -> bool:
    """Start the daemon detached; False if one is already alive."""
    resolved = paths or daemon_paths()
    if is_daemon_alive(resolved.socket):
        return False
    resolved.pid.parent.mkdir(parents=True, exist_ok=True)
    from agentwatch.rotating_log import RotatingLog

    with RotatingLog(resolved.log).open_append() as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "agentwatch.daemon"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            env=_child_env(),
        )
    deadline = time.time() + _DAEMON_START_TIMEOUT_SECONDS
    while time.time() < deadline:
        if is_daemon_alive(resolved.socket):
            resolved.pid.write_text(str(process.pid), encoding="utf-8")
            return True
        if process.poll() is not None:
            break
        time.sleep(0.05)
    raise InstallError(f"daemon failed to start; see {resolved.log}")


def stop_daemon(paths: DaemonPaths | None = None) -> bool:
    """Stop the daemon by its pid file; False if no pid file exists."""
    resolved = paths or daemon_paths()
    if not resolved.pid.exists():
        return False
    try:
        pid = int(resolved.pid.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        resolved.pid.unlink(missing_ok=True)
        return False
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + _DAEMON_STOP_TIMEOUT_SECONDS
    while time.time() < deadline and is_daemon_alive(resolved.socket):
        time.sleep(0.05)
    resolved.pid.unlink(missing_ok=True)
    return True


def _mcp_proxy_paths() -> tuple[Path, Path]:
    """Resolve the MCP proxy pid/log files under the store directory."""
    from agentwatch.configuration import load_config

    base = Path(load_config().store.path).expanduser()
    return base / "mcp-proxy.pid", base / "mcp-proxy.log"


def _port_in_use(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.settimeout(0.3)
        probe.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def start_mcp_proxy(
    routes: Mapping[str, str],
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    socket_path: str | None = None,
) -> int:
    """Start the long-lived HTTP/SSE MCP proxy detached; return its pid.

    Fails closed when ``port`` is already in use (D-M6), so a silent second
    instance never shadows the configured routes.
    """
    if not routes:
        raise InstallError("start_mcp_proxy requires at least one HTTP/SSE route")
    if _port_in_use(host, port):
        raise InstallError(f"MCP proxy port {port} is already in use")
    pid_path, log_path = _mcp_proxy_paths()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable,
        "-m",
        "agentwatch.mcp_proxy",
        "--http",
        "--host",
        host,
        "--port",
        str(port),
    ]
    for name, url in routes.items():
        argv += ["--route", f"{name}={url}"]
    if socket_path is not None:
        argv += ["--socket", socket_path]
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            env=_child_env(),
        )
    deadline = time.time() + _DAEMON_START_TIMEOUT_SECONDS
    while time.time() < deadline:
        if _port_in_use(host, port):
            pid_path.write_text(str(process.pid), encoding="utf-8")
            return process.pid
        if process.poll() is not None:
            break
        time.sleep(0.05)
    raise InstallError(f"MCP proxy failed to start; see {log_path}")


def stop_mcp_proxy() -> bool:
    """Stop the MCP proxy by its pid file; False if no pid file exists."""
    pid_path, _ = _mcp_proxy_paths()
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pid_path.unlink(missing_ok=True)
        return False
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + _DAEMON_STOP_TIMEOUT_SECONDS
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.05)
    pid_path.unlink(missing_ok=True)
    return True


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - process owned by another user
        return True
    return True


_TESTED_CLAUDE_MAJOR = 2


def preflight(claude_version: str | None) -> list[str]:
    """Return non-blocking warnings about the harness environment (G4).

    Warns (never blocks): a missing/unparseable/untested Claude Code version, and
    (via the caller) project-scope hooks not firing in untrusted headless runs.
    """
    warnings: list[str] = []
    if claude_version is None:
        warnings.append(
            "claude CLI not found on PATH; install Claude Code before relying on recording"
        )
        return warnings
    match = re.search(r"(\d+)\.(\d+)", claude_version)
    if match is None:
        warnings.append(f"could not parse claude version {claude_version!r}")
        return warnings
    if int(match.group(1)) != _TESTED_CLAUDE_MAJOR:
        warnings.append(
            f"claude {claude_version} is outside the tested {_TESTED_CLAUDE_MAJOR}.x range; "
            "hook behavior may differ"
        )
    return warnings


def detect_claude_version() -> str | None:
    """Return the installed ``claude --version`` string, or None if unavailable."""
    executable = shutil.which("claude")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - environment-specific
        return None
    text = result.stdout.strip() or result.stderr.strip()
    return text or None
