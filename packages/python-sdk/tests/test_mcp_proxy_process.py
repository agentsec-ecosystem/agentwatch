"""Background MCP proxy process lifecycle tests (M10 N1 #212)."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from agentwatch.install import InstallError, start_mcp_proxy, stop_mcp_proxy


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_start_and_stop_mcp_proxy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    port = _free_port()
    routes = {"echo": "http://127.0.0.1:1/"}
    pid = start_mcp_proxy(routes, port=port)
    try:
        assert pid > 0
        assert (tmp_path / "mcp-proxy.pid").read_text().strip() == str(pid)
        # A second instance on the same port fails closed (D-M6).
        with pytest.raises(InstallError):
            start_mcp_proxy(routes, port=port)
    finally:
        assert stop_mcp_proxy() is True
    assert not (tmp_path / "mcp-proxy.pid").exists()


def test_start_mcp_proxy_requires_a_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    with pytest.raises(InstallError):
        start_mcp_proxy({}, port=_free_port())


def test_stop_mcp_proxy_without_a_pid_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    assert stop_mcp_proxy() is False
