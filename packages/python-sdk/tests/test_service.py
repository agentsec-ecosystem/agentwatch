"""Service supervision unit-file tests (M12 K3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentwatch.service import (
    SYSTEMD_UNIT_NAME,
    install_service,
    render_unit,
    uninstall_service,
)


def test_launchd_unit_has_label_and_arguments() -> None:
    unit = render_unit("darwin", python="/usr/bin/python3")

    assert unit.platform == "darwin"
    assert unit.path.name.endswith(".plist")
    assert "com.agentsec.agentwatch" in unit.content
    assert "/usr/bin/python3" in unit.content
    assert "agentwatch.daemon" in unit.content


def test_systemd_unit_has_service_and_install_sections() -> None:
    unit = render_unit("linux", python="/usr/bin/python3")

    assert unit.platform == "linux"
    assert unit.path.name == SYSTEMD_UNIT_NAME
    assert "[Service]" in unit.content
    assert "ExecStart=/usr/bin/python3 -m agentwatch.daemon" in unit.content
    assert "[Install]" in unit.content


def test_unsupported_platform_is_rejected() -> None:
    with pytest.raises(ValueError):
        render_unit("windows")


def test_install_and_uninstall_unit(tmp_path: Path) -> None:
    unit = render_unit("linux", python="/usr/bin/python3")
    target = tmp_path / "agentwatch.service"

    path = install_service(unit, path=target)

    assert path.read_text(encoding="utf-8") == unit.content
    assert uninstall_service(unit, path=target) is True
    assert not target.exists()
    assert uninstall_service(unit, path=target) is False
