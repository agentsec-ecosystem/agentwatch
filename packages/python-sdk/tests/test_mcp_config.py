"""MCP config install/restore tests (M10 N1 #212)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch.mcp_config import (
    McpConfigError,
    McpConfigTarget,
    McpProxyCommand,
    install_mcp_proxy,
    mcp_proxy_installed,
    resolve_mcp_proxy_command,
    resolve_mcp_scope,
    uninstall_mcp_proxy,
)

PROXY = McpProxyCommand(command="agentwatch-mcp-proxy")


def _target(tmp_path: Path) -> McpConfigTarget:
    return resolve_mcp_scope("project", cwd=tmp_path)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_resolve_mcp_scope_project_and_user(tmp_path: Path) -> None:
    project = resolve_mcp_scope("project", cwd=tmp_path)
    assert project.path == tmp_path / ".mcp.json"
    user = resolve_mcp_scope("user", home=tmp_path)
    assert user.path == tmp_path / ".claude.json"
    with pytest.raises(McpConfigError):
        resolve_mcp_scope("bogus", cwd=tmp_path)


def test_install_repoints_stdio_and_preserves_keys(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    original = {
        "mcpServers": {
            "github": {
                "command": "node",
                "args": ["server.js", "--flag"],
                "env": {"TOKEN": "x"},
                "type": "stdio",
            },
            "unrelated": {"command": "keep"},
        },
        "otherSetting": True,
    }
    _write(path, json.dumps(original))

    report = install_mcp_proxy(_target(tmp_path), proxy_command=PROXY, port=8765)

    assert report.repointed == ("github", "unrelated")
    data = json.loads(path.read_text())
    github = data["mcpServers"]["github"]
    assert github["command"] == "agentwatch-mcp-proxy"
    assert github["args"] == ["--server", "github", "--", "node", "server.js", "--flag"]
    assert github["env"] == {"TOKEN": "x"}  # preserved
    assert github["type"] == "stdio"  # preserved
    assert data["otherSetting"] is True
    assert mcp_proxy_installed(_target(tmp_path))


def test_install_repoints_http_route(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    _write(path, json.dumps({"mcpServers": {"remote": {"url": "https://example.com/mcp"}}}))

    report = install_mcp_proxy(
        _target(tmp_path), proxy_command=PROXY, port=8765
    )

    assert report.http_routes == {"remote": "https://example.com/mcp"}
    assert json.loads(path.read_text())["mcpServers"]["remote"]["url"] == (
        "http://127.0.0.1:8765/remote"
    )


def test_install_selects_named_servers_and_reports_skipped(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    _write(path, json.dumps({"mcpServers": {"a": {"command": "a"}, "b": {"command": "b"}}}))

    report = install_mcp_proxy(
        _target(tmp_path),
        proxy_command=PROXY,
        port=8765,
        servers=["a", "missing"],
    )

    assert report.repointed == ("a",)
    assert report.skipped == ("missing",)
    data = json.loads(path.read_text())
    assert data["mcpServers"]["b"]["command"] == "b"  # untouched


def test_install_creates_file_and_uninstall_deletes_it(tmp_path: Path) -> None:
    report = install_mcp_proxy(_target(tmp_path), proxy_command=PROXY, port=8765)
    assert report.created
    path = tmp_path / ".mcp.json"
    assert path.exists()

    result = uninstall_mcp_proxy(_target(tmp_path))
    assert result.deleted
    assert not path.exists()
    assert not mcp_proxy_installed(_target(tmp_path))


def test_uninstall_restores_bytes_identically(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    # Deliberately unusual formatting: no trailing newline, tab-ish spacing.
    original = '{"mcpServers":{"s":{"command":"run","args":["a"]}},"x":1}'
    _write(path, original)

    install_mcp_proxy(_target(tmp_path), proxy_command=PROXY, port=8765)
    assert path.read_text() != original

    result = uninstall_mcp_proxy(_target(tmp_path))
    assert result.restored
    assert path.read_text() == original  # byte-identical


def test_uninstall_fails_closed_when_file_changed(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    _write(path, json.dumps({"mcpServers": {"s": {"command": "run"}}}))
    install_mcp_proxy(_target(tmp_path), proxy_command=PROXY, port=8765)

    edited = path.read_text() + "\n"
    _write(path, edited)
    result = uninstall_mcp_proxy(_target(tmp_path))

    assert not result.restored
    assert "changed" in (result.reason or "")
    assert path.read_text() == edited  # left untouched


def test_install_refuses_unparseable_file(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    _write(path, "not json")
    with pytest.raises(McpConfigError):
        install_mcp_proxy(_target(tmp_path), proxy_command=PROXY, port=8765)
    assert path.read_text() == "not json"


def test_uninstall_reports_not_installed(tmp_path: Path) -> None:
    result = uninstall_mcp_proxy(_target(tmp_path))
    assert result.reason == "not installed"


def test_resolve_mcp_proxy_command_falls_back_to_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("agentwatch.mcp_config.shutil.which", lambda _name: None)
    command = resolve_mcp_proxy_command(str(tmp_path / "python"))
    assert command.args_prefix == ("-m", "agentwatch.mcp_proxy")
    assert command.args_for("s", "cmd", ["a"]) == [
        "-m",
        "agentwatch.mcp_proxy",
        "--server",
        "s",
        "--",
        "cmd",
        "a",
    ]
