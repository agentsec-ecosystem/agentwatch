"""CLI tests for ``agentwatch init --mcp-proxy`` + uninstall restore (M10 N1 #212)."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from agentwatch.cli import main as cli_main
from agentwatch.install import InstallError

cli_main_module = importlib.import_module("agentwatch.cli.main")


def _write(path: Path, data: object) -> None:
    path.write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )


def test_init_mcp_proxy_dry_run_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["init", "--mcp-proxy", "--dry-run"])

    assert rc == 0
    assert "would re-point MCP config" in capsys.readouterr().out
    assert not (tmp_path / ".mcp.json").exists()


def test_init_mcp_proxy_repoints_stdio_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / ".mcp.json",
        {"mcpServers": {"github": {"command": "node", "args": ["s.js"]}}},
    )

    rc = cli_main(["init", "--mcp-proxy", "--no-daemon"])

    assert rc == 0
    data = json.loads((tmp_path / ".mcp.json").read_text())
    entry = data["mcpServers"]["github"]
    assert entry["command"] != "node"
    assert entry["args"][-3:] == ["--", "node", "s.js"]
    assert (tmp_path / ".mcp.json.agentwatch-mcp-manifest.json").exists()


def test_init_mcp_proxy_starts_http_proxy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".mcp.json", {"mcpServers": {"remote": {"url": "https://example.com/mcp"}}})
    captured: dict[str, object] = {}

    def fake_start(routes: dict[str, str], **kwargs: object) -> int:
        captured["routes"] = routes
        return 4242

    monkeypatch.setattr(cli_main_module, "start_mcp_proxy", fake_start)
    rc = cli_main(["init", "--mcp-proxy", "--no-daemon"])

    assert rc == 0
    assert captured["routes"] == {"remote": "https://example.com/mcp"}


def test_init_mcp_proxy_rolls_back_when_proxy_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    original = {"mcpServers": {"remote": {"url": "https://example.com/mcp"}}}
    _write(tmp_path / ".mcp.json", original)

    def fail_start(routes: dict[str, str], **kwargs: object) -> int:
        raise InstallError("port busy")

    monkeypatch.setattr(cli_main_module, "start_mcp_proxy", fail_start)
    rc = cli_main(["init", "--mcp-proxy", "--no-daemon"])

    assert rc == 1
    assert json.loads((tmp_path / ".mcp.json").read_text()) == original


def test_init_mcp_proxy_refuses_unparseable_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".mcp.json", "not json")

    rc = cli_main(["init", "--mcp-proxy", "--no-daemon"])

    assert rc == 1
    assert (tmp_path / ".mcp.json").read_text() == "not json"


def test_uninstall_restores_mcp_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    original_text = '{"mcpServers":{"s":{"command":"run"}}}'
    _write(tmp_path / ".mcp.json", original_text)

    cli_main(["init", "--mcp-proxy", "--no-daemon"])
    assert (tmp_path / ".mcp.json").read_text() != original_text

    monkeypatch.setattr(cli_main_module, "stop_daemon", lambda: False)
    monkeypatch.setattr(cli_main_module, "stop_mcp_proxy", lambda: True)
    rc = cli_main(["uninstall"])

    assert rc == 0
    assert (tmp_path / ".mcp.json").read_text() == original_text
    out = capsys.readouterr().out
    assert "MCP config restored" in out
    assert "mcp proxy: stopped" in out


def test_uninstall_reports_not_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_main_module, "stop_daemon", lambda: False)
    monkeypatch.setattr(cli_main_module, "stop_mcp_proxy", lambda: False)

    assert cli_main(["uninstall"]) == 0
    assert "MCP config not installed" in capsys.readouterr().out
