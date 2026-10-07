"""CLI tests for ``agentwatch a2a-proxy`` (M29 A2A-1 #364)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agentwatch import a2a_proxy
from agentwatch.cli import main

ECHO = Path(__file__).resolve().parent / "fixtures" / "a2a" / "echo_agent.py"


def test_cli_a2a_proxy_requires_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["a2a-proxy", "--agent", "echo"]) == 2
    assert "requires" in capsys.readouterr().err


def test_cli_a2a_proxy_relays_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_stdio(agent: str, command: list[str], **_: object) -> int:
        captured["agent"] = agent
        captured["command"] = list(command)
        return 0

    monkeypatch.setattr(a2a_proxy, "run_stdio", fake_run_stdio)
    rc = main(["a2a-proxy", "--agent", "echo", "--", sys.executable, str(ECHO)])

    assert rc == 0
    assert captured == {"agent": "echo", "command": [sys.executable, str(ECHO)]}


def test_cli_a2a_proxy_http_relays_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_serve_http(routes: dict[str, str], **kwargs: object) -> int:
        captured["routes"] = routes
        captured["port"] = kwargs.get("port")
        return 0

    monkeypatch.setattr(a2a_proxy, "serve_http", fake_serve_http)
    rc = main(
        ["a2a-proxy", "--http", "--port", "9999", "--route", "echo=http://127.0.0.1:1234/"]
    )

    assert rc == 0
    assert captured == {"routes": {"echo": "http://127.0.0.1:1234/"}, "port": 9999}


def test_cli_a2a_proxy_http_rejects_a_malformed_route(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["a2a-proxy", "--http", "--route", "echo"]) == 2
    assert "invalid route" in capsys.readouterr().err