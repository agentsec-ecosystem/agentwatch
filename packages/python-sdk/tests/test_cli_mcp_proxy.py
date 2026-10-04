"""CLI tests for ``agentwatch mcp-proxy`` (M10 N1 #83)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agentwatch import mcp_proxy
from agentwatch.cli import main

ECHO = Path(__file__).resolve().parent / "fixtures" / "mcp" / "echo_server.py"


def test_cli_mcp_proxy_requires_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["mcp-proxy", "--server", "echo"]) == 2
    assert "requires" in capsys.readouterr().err


def test_cli_mcp_proxy_relays_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_stdio(server: str, command: list[str], **_: object) -> int:
        captured["server"] = server
        captured["command"] = list(command)
        return 0

    monkeypatch.setattr(mcp_proxy, "run_stdio", fake_run_stdio)
    rc = main(["mcp-proxy", "--server", "echo", "--", sys.executable, str(ECHO)])

    assert rc == 0
    assert captured == {"server": "echo", "command": [sys.executable, str(ECHO)]}


def test_cli_mcp_proxy_http_relays_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_serve_http(routes: dict[str, str], **kwargs: object) -> int:
        captured["routes"] = routes
        captured["port"] = kwargs.get("port")
        return 0

    monkeypatch.setattr(mcp_proxy, "serve_http", fake_serve_http)
    rc = main(
        ["mcp-proxy", "--http", "--port", "9999", "--route", "echo=http://127.0.0.1:1234/"]
    )

    assert rc == 0
    assert captured == {"routes": {"echo": "http://127.0.0.1:1234/"}, "port": 9999}


def test_cli_mcp_proxy_http_rejects_a_malformed_route(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["mcp-proxy", "--http", "--route", "echo"]) == 2
    assert "invalid route" in capsys.readouterr().err


def test_cli_mcp_proxy_http_requires_a_route(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["mcp-proxy", "--http"]) == 2
    assert "requires" in capsys.readouterr().err

