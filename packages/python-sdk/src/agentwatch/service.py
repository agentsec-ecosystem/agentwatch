"""Optional service supervision (M12 K3, PRD 28).

F1 assumes a supervisor restarts the daemon; a bare detached process ends
recording at reboot. ``agentwatch init --service`` (opt-in, consent-first — never
default) generates a launchd user agent (macOS) or a systemd user unit (Linux);
``uninstall`` removes it.
"""

from __future__ import annotations

import plistlib
import sys
from dataclasses import dataclass
from pathlib import Path

from agentwatch import posture

LABEL = "com.agentsec.agentwatch"
SYSTEMD_UNIT_NAME = "agentwatch.service"
LAUNCHD_UNIT_NAME = f"{LABEL}.plist"


@dataclass(frozen=True)
class ServiceUnit:
    """A generated service unit: its platform, conventional path, and content."""

    platform: str
    path: Path
    content: str


def _program(python: str | None) -> tuple[str, list[str]]:
    interpreter = python or sys.executable
    return interpreter, [interpreter, "-m", "agentwatch.daemon"]


def default_unit_path(platform: str) -> Path:
    if platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / LAUNCHD_UNIT_NAME
    if platform == "linux":
        return Path.home() / ".config" / "systemd" / "user" / SYSTEMD_UNIT_NAME
    raise ValueError(f"unsupported service platform {platform!r}; expected 'darwin' or 'linux'")


def render_unit(platform: str, *, python: str | None = None) -> ServiceUnit:
    """Render the service unit for ``darwin`` or ``linux``."""
    if platform == "darwin":
        interpreter, arguments = _program(python)
        plist = {
            "Label": LABEL,
            "ProgramArguments": arguments,
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardOutPath": str(Path.home() / "Library" / "Logs" / "agentwatch.log"),
            "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "agentwatch.log"),
            "ProcessType": "Background",
            "EnvironmentVariables": {"AGENTWATCH_SERVICE": "1"},
        }
        content = plistlib.dumps(plist).decode("utf-8")
        return ServiceUnit(platform, default_unit_path(platform), content)

    if platform == "linux":
        interpreter, arguments = _program(python)
        exec_start = " ".join(arguments)
        content = (
            "[Unit]\n"
            "Description=agentwatch local-first recorder daemon\n"
            "After=default.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={exec_start}\n"
            "Restart=on-failure\n"
            "Environment=AGENTWATCH_SERVICE=1\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        return ServiceUnit(platform, default_unit_path(platform), content)

    raise ValueError(f"unsupported service platform {platform!r}; expected 'darwin' or 'linux'")


def install_service(unit: ServiceUnit, *, path: Path | None = None) -> Path:
    """Write the unit file (0600), returning its path."""
    target = path or unit.path
    posture.secure_dir(target.parent)
    target.write_text(unit.content, encoding="utf-8")
    posture.secure_file(target)
    return target


def uninstall_service(unit: ServiceUnit, *, path: Path | None = None) -> bool:
    """Remove the unit file; return whether one was present."""
    target = path or unit.path
    if not target.exists():
        return False
    target.unlink()
    return True
