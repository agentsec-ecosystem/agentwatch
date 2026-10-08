"""`agentwatch ui` read-only loopback console (M30 LUI-1, PRD 54 §LUI-1, ADR-0036).

One command opens a **loopback-only, token-gated, read-only** browser console
over the chain store. The security model is enumerated by tests: loopback bind,
per-launch token, host-header (DNS-rebinding) check, no mutation endpoints, and
no egress. UI numbers equal the CLI ``--json`` (parity).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.egress_audit import audit
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore
from agentwatch.ui import ConsoleServer

SRC = Path(__file__).resolve().parents[1] / "src" / "agentwatch"
START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _agent() -> AgentIdentity:
    return AgentIdentity(identity="agent")


def _tool(
    session: str,
    name: str,
    *,
    arguments: dict[str, object] | None = None,
    minute: int = 0,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=_agent(),
        tool=ToolCall(name=name, arguments=arguments) if arguments else ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        project="/repo",
        step_type=StepType.ACT,
    )


def _usage(session: str, tokens: int, model: str, *, minute: int = 0) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent", model_version=model),
        tool=ToolCall(name="session-usage"),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        project="/repo",
        tokens=tokens,
        step_type=StepType.OBSERVE,
    )


def _store(directory: Path) -> RecordStore:
    directory.mkdir(parents=True, exist_ok=True)
    store = RecordStore(directory / "records.jsonl")
    store.append(_tool("s1", "Bash", arguments={"command": "ls"}))
    store.append(
        _tool("s1", "Write", arguments={"file_path": "/repo/app.py"}, minute=1)
    )
    store.append(_tool("s2", "Read", minute=2))
    store.append(_usage("s1", 1200, "claude-3-5-sonnet-20241022", minute=3))
    return store


def _request(
    url: str,
    *,
    token: str | None = None,
    host_header: str | None = None,
    method: str = "GET",
) -> tuple[int, str]:
    headers: dict[str, str] = {}
    if token is not None:
        headers["X-Agentwatch-Token"] = token
    request = urllib.request.Request(url, method=method, headers=headers)
    if host_header is not None:
        request.add_unredirected_header("Host", host_header)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - loopback test
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_console_serves_the_overview(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        status, body = _request(server.url + "/", token=server.token)
        assert status == 200
        assert "agentwatch" in body.lower()
        assert "read-only" in body.lower()

        status, payload = _request(server.url + "/api/sessions", token=server.token)
        assert status == 200
        sessions = json.loads(payload)["sessions"]
        assert [item["session_id"] for item in sessions] == ["s1", "s2"]


def test_console_requires_a_token(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        for path in ("/", "/api/sessions", "/api/cost"):
            assert _request(server.url + path)[0] == 403
            assert _request(server.url + path, token="wrong-token")[0] == 403


def test_console_rejects_a_non_loopback_host_header(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        status, _ = _request(
            server.url + "/api/sessions", token=server.token, host_header="evil.example.com"
        )
        assert status == 403


def test_console_has_no_mutation_endpoints(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, _ = _request(
                server.url + "/api/sessions", token=server.token, method=method
            )
            assert status == 405


def test_console_binds_loopback_even_when_asked_otherwise(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store, host="0.0.0.0") as server:
        assert server.address[0] in {"127.0.0.1", "::1", "localhost"}


def test_console_renders_gaps(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Tamper the chain: the console must still serve and must show the gap.
    text = store.path.read_text(encoding="utf-8")
    store.path.write_text(text.replace('"s2"', '"sX"', 1), encoding="utf-8")
    broken = RecordStore(store.path)
    with ConsoleServer(broken) as server:
        status, payload = _request(server.url + "/api/health", token=server.token)
        assert status == 200
        health = json.loads(payload)
        assert health["chain_ok"] is False

        status, body = _request(server.url + "/", token=server.token)
        assert status == 200
        assert "chain" in body.lower()


def test_console_export_is_read_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    before = store.path.read_bytes()
    with ConsoleServer(store) as server:
        status, body = _request(server.url + "/api/export/s1", token=server.token)
        assert status == 200
        assert all(json.loads(line)["record"]["session_id"] == "s1" for line in body.splitlines())
    assert store.path.read_bytes() == before


def test_console_module_is_egress_clean() -> None:
    assert audit(SRC) == []


def test_console_ui_cli_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    store_dir = tmp_path / "store"
    store = _store(store_dir)
    with ConsoleServer(store) as server:
        _, body = _request(server.url + "/api/impact/s1", token=server.token)
        assert json.loads(body) == _cli_json(capsys, store_dir, "impact", "s1", "--json")

        _, body = _request(server.url + "/api/cost", token=server.token)
        assert json.loads(body) == _cli_json(capsys, store_dir, "cost", "--json")

        _, body = _request(server.url + "/api/coverage", token=server.token)
        assert json.loads(body) == _cli_json(capsys, store_dir, "coverage", "--json")


def _cli_json(
    capsys: pytest.CaptureFixture[str], store_dir: Path, *args: str
) -> object:
    capsys.readouterr()
    assert main(["--set", f"store.path={store_dir}", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_cli_ui_check_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    _store(store_dir)
    rc = main(["--set", f"store.path={store_dir}", "ui", "--check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "http://127.0.0.1:" in out
    assert "read-only" in out.lower()
