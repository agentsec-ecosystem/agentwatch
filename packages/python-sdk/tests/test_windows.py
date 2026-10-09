"""Windows service-unit generation tests (M27 WIN-1 #350).

Windows has no launchd/systemd; ``agentwatch init --service`` renders a Task
Scheduler XML that runs the daemon at logon (least privilege). Rendering and the
unit path are pure and tested on every OS; the actual Windows CI leg runs in
``.github/workflows/windows.yml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentwatch.service import (
    WINDOWS_TASK_NAME,
    default_unit_path,
    install_service,
    render_unit,
    uninstall_service,
)


def test_windows_task_runs_the_daemon() -> None:
    unit = render_unit("win32", python="C:\\Python\\python.exe")

    assert unit.platform == "win32"
    assert unit.path.name == WINDOWS_TASK_NAME
    assert "<Task" in unit.content
    assert "<LogonTrigger>" in unit.content
    assert "C:\\Python\\python.exe" in unit.content
    assert "-m agentwatch.daemon" in unit.content
    assert "<RunLevel>LeastPrivilege</RunLevel>" in unit.content


def test_windows_unit_path_is_under_appdata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    unit_path = default_unit_path("win32")

    assert str(unit_path).startswith(str(tmp_path))
    assert unit_path.name == WINDOWS_TASK_NAME


def test_windows_unit_installs_and_uninstalls(tmp_path: Path) -> None:
    unit = render_unit("win32", python="C:\\Python\\python.exe")
    path = tmp_path / WINDOWS_TASK_NAME

    installed = install_service(unit, path=path)
    assert installed.read_text(encoding="utf-8").startswith("<?xml")

    assert uninstall_service(unit, path=path) is True
    assert not path.exists()
