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
import shutil
import signal
import socket
import subprocess
import sys
import time
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

    def handler(self, phase: str) -> dict[str, Any]:
        return {"type": "command", "command": self.command, "args": [*self.args_prefix, phase]}


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


def install_hooks(settings_path: Path, command: HookCommand) -> None:
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
        groups.append({"matcher": "*", "hooks": [command.handler(phase)]})
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
    with resolved.log.open("ab") as log:
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
