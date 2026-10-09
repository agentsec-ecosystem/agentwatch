"""`agentwatch ui` read-only loopback console (M30 LUI-1, PRD 54 §LUI-1, ADR-0036).

One command opens a **loopback-only, token-gated, read-only** browser console
over the chain store. The security model is enumerated by tests: loopback bind,
per-launch token, host-header (DNS-rebinding) check, no mutation endpoints, and
no egress. UI numbers equal the CLI ``--json`` (parity).
"""

from __future__ import annotations

import http.client
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
    outcome: Outcome = Outcome.OK,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=_agent(),
        tool=ToolCall(name=name, arguments=arguments) if arguments else ToolCall(name=name),
        outcome=outcome,
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


def test_live_timeline_backfills_existing_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        status, body = _request(server.url + "/api/live/timeline", token=server.token)
        assert status == 200
        payload = json.loads(body)
        assert payload["degraded"] is False
        assert payload["gaps"] == []
        assert len(payload["lines"]) == 4


def test_live_timeline_emits_new_records_only_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store) as server:
        _request(server.url + "/api/live/timeline", token=server.token)
        store.append(_tool("s3", "Grep"))

        _, body = _request(server.url + "/api/live/timeline", token=server.token)
        payload = json.loads(body)
        assert len(payload["lines"]) == 1
        assert payload["gaps"] == []


def test_live_anomaly_inbox_surfaces_failures(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append(_tool("s3", "Bash", outcome=Outcome.ERROR))
    store.append(_tool("s3", "Bash", outcome=Outcome.DENIED, minute=1))
    with ConsoleServer(store) as server:
        status, body = _request(server.url + "/api/live/anomalies", token=server.token)
        assert status == 200
        payload = json.loads(body)
        assert len(payload["anomalies"]) == 2
        assert {item["record"]["outcome"] for item in payload["anomalies"]} == {"error", "denied"}


def test_live_shows_degraded_when_backpressured(tmp_path: Path) -> None:
    from agentwatch.streaming import Subscriber

    subscriber: Subscriber[int] = Subscriber(1)
    subscriber.offer(0)
    subscriber.offer(1)  # overflow -> degraded
    store = _store(tmp_path)
    with ConsoleServer(store, subscriber=subscriber) as server:
        _, body = _request(server.url + "/api/live/timeline", token=server.token)
        assert json.loads(body)["degraded"] is True


def test_console_signatures_match_the_digest(tmp_path: Path) -> None:
    from agentwatch.digest import build_digest

    now = datetime.now(timezone.utc)
    directory = tmp_path / "window"
    directory.mkdir()
    store = RecordStore(directory / "records.jsonl")
    for minute in (0, 1):
        store.append(
            AgentRecord(
                session_id="s1",
                agent=_agent(),
                tool=ToolCall(name="Bash"),
                outcome=Outcome.ERROR,
                started_at=now - timedelta(minutes=minute),
                project="/repo",
                step_type=StepType.ACT,
            )
        )

    report = build_digest(store, now=now)
    with ConsoleServer(store) as server:
        status, body = _request(server.url + "/api/signatures", token=server.token)
        assert status == 200
        payload = json.loads(body)

    assert payload["signatures_version"] == report.signatures_version == "sg1"
    assert payload["signatures"], "expected at least one recurring failure signature"
    assert len(payload["signatures"]) == len(report.signatures)
    top = payload["signatures"][0]
    assert top["tool"] == "Bash"
    assert top["count"] == 2
    assert any(link.startswith("replay ") for link in top["evidence"])


def test_live_stream_is_sse(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with ConsoleServer(store, poll_interval=0.05) as server:
        connection = http.client.HTTPConnection(server.address[0], server.address[1], timeout=5)
        try:
            connection.request(
                "GET",
                "/api/live/stream",
                headers={"X-Agentwatch-Token": server.token},
            )
            response = connection.getresponse()
            assert response.status == 200
            assert response.getheader("Content-Type", "").startswith("text/event-stream")
            line = response.fp.readline().decode("utf-8")
            assert line.startswith("data: ")
            payload = json.loads(line.removeprefix("data: ").strip())
            assert len(payload["lines"]) == 4
        finally:
            connection.close()

