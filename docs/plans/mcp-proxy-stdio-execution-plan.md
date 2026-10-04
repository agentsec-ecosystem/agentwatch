# MCP Interposition Proxy — Plan A (Adapter + stdio + daemon + conformance) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every MCP `tools/call` request/response from a stdio MCP server as chained agentwatch records, end to end through the daemon.

**Architecture:** A new `mcp_proxy` adapter normalizes JSON-RPC frames to records; a stdio proxy relays a harness's stdin/stdout to a spawned MCP server unchanged while emitting frames to the daemon over the existing Unix socket; the daemon routes the new `mcp` phase through the adapter so redaction, secret detection, dedup, and the hash chain are reused unchanged.

**Tech Stack:** Python 3.10+ stdlib (`argparse`, `json`, `subprocess`, `threading`, `socket`); `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** [`docs/design/mcp-proxy-design.md`](../design/mcp-proxy-design.md) · WBS [Part 6](../wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md) 10.5/10.N1 · PRD [27](../prd/27-harness-expansion.md#n1-mcp-client-interposition-adapter-one-adapter-n-harnesses--m10-212) · decision D-P.

## Global Constraints

- Python 3.10+ stdlib only; no new runtime dependency (NFR-5).
- Fail closed, never silent (PRD 17); redaction before storage (DD-06); monitor-only (R2); local-first, no egress (R6).
- Frame keys stay fixed (`phase`, `harness`, `event`); `phase: "mcp"` is an additive change to `protocol.FRAME_PHASES`.
- `schema_version` stays `0.1.0`; additive record changes only.
- Every adapter declares `CAPABILITIES` and `DOCUMENTED_GAPS` disjointly; conformance blocks CI.
- Coverage ≥ 95%, `ruff` zero, `mypy --strict` clean (NFR-11).
- Run package tests from `packages/python-sdk` (`cd packages/python-sdk && python -m pytest …`).

## Review Focus

The spec implies these and no task's happy-path tests exercise them; each gets a test in its owning task:

1. A server response whose `id` was never seen (or is a duplicate) — must be relayed and **not** recorded, never crash (Task 6).
2. An out-of-order response (before its request) — not paired, no crash (Task 6).
3. A JSON-RPC **batch** (top-level array) — relayed unchanged, not recorded as a tool call (Task 5/6).
4. A line with no trailing newline at EOF, or binary garbage — forwarded unchanged; parse failure contained (Task 6).
5. A response frame missing `tool_name` — rejected by the adapter, never recorded with a wrong name (Task 1).

---

### Task 1: MCP adapter module

**Files:**
- Create: `packages/python-sdk/src/agentwatch/adapters/mcp_proxy.py`
- Test: `packages/python-sdk/tests/test_mcp_proxy_adapter.py`

**Interfaces:**
- Produces: `HARNESS_ID: str = "mcp-proxy"`; `CAPABILITIES: frozenset[str] = frozenset({"mcp-tools"})`; `DOCUMENTED_GAPS: tuple[str, ...] = ("mcp-resources", "mcp-prompts", "mcp-sampling")`; `class McpProxyAdapterError(ValueError)`; `normalize(message: Mapping[str, Any], *, redaction: RedactionConfig | None = None) -> list[AgentRecord]`.
- Consumes: `agentwatch.records` (`AgentRecord`, `AgentIdentity`, `ToolCall`, `Outcome`, `StepType`, `RecordPrivacyMode`, `SecurityEvent`, `SecurityEventType`, `_parse_iso`), `agentwatch.secrets.redact_mapping`, `agentwatch.redact` (`PrivacyMode`, `RedactionConfig`).

- [ ] **Step 1: Write the failing tests**

```python
# packages/python-sdk/tests/test_mcp_proxy_adapter.py
from __future__ import annotations

import pytest

from agentwatch.adapters import mcp_proxy
from agentwatch.records import SecurityEventType


def _request(**event_overrides):
    event = {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"number": 3}},
        },
        "timestamp": "2026-01-02T03:04:05+00:00",
        "cwd": "/repo",
    }
    event.update(event_overrides)
    return {"phase": "mcp", "harness": "mcp-proxy", "event": event}


def test_request_becomes_an_intent_record():
    records = mcp_proxy.normalize(_request())
    assert len(records) == 1
    assert records[0].to_dict() == {
        "schema_version": "0.1.0",
        "session_id": "s-1",
        "agent": {"identity": "unknown"},
        "tool": {"name": "issue_get", "server": "github"},
        "outcome": "ok",
        "started_at": "2026-01-02T03:04:05+00:00",
        "trace_id": "s-1",
        "span_id": "mcp:github:7",
        "harness": "mcp-proxy",
        "project": "/repo",
        "step_type": "act",
    }


def test_response_becomes_an_outcome_record():
    message = _request(
        direction="response",
        tool_name="issue_get",
        rpc={"jsonrpc": "2.0", "id": 7, "result": {"ok": True}},
        timestamp="2026-01-02T03:04:06+00:00",
    )
    record = mcp_proxy.normalize(message)[0].to_dict()
    assert record["step_type"] == "observe"
    assert record["outcome"] == "ok"
    assert record["span_id"] == "mcp:github:7"
    assert record["tool"] == {"name": "issue_get", "server": "github"}
    assert record["ended_at"] == "2026-01-02T03:04:06+00:00"


def test_error_response_is_an_error_outcome():
    message = _request(
        direction="response",
        tool_name="issue_get",
        rpc={"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "boom"}},
    )
    assert mcp_proxy.normalize(message)[0].outcome.value == "error"


def test_response_without_tool_name_is_rejected():
    message = _request(direction="response", rpc={"jsonrpc": "2.0", "id": 7, "result": {}})
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(message)


@pytest.mark.parametrize("phase", [*mcp_proxy.DOCUMENTED_GAPS, "__unsupported-conformance-phase__"])
def test_unsupported_phase_is_rejected(phase):
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize({"phase": phase, "event": {}})


def test_non_tools_call_method_is_rejected():
    message = _request(rpc={"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {}})
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize(message)


def test_secret_in_arguments_fires_secret_detected_and_is_not_stored():
    message = _request(
        rpc={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "issue_get", "arguments": {"cmd": "export TOKEN=sk-abcdefgh"}},
        }
    )
    record = mcp_proxy.normalize(message)[0]
    assert record.security_event is not None
    assert record.security_event.type is SecurityEventType.SECRET_DETECTED
    assert "sk-abcdefgh" not in str(record.to_dict())


def test_missing_id_means_no_span_id():
    message = _request(rpc={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "x"}})
    assert mcp_proxy.normalize(message)[0].span_id is None


def test_malformed_event_is_rejected():
    with pytest.raises(mcp_proxy.McpProxyAdapterError):
        mcp_proxy.normalize({"phase": "mcp", "event": "not-an-object"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: agentwatch.adapters.mcp_proxy`.

- [ ] **Step 3: Implement `normalize`**

Mirror `agentwatch/adapters/claude_code.py`'s structure and helper style. Requirements the tests pin:

- `normalize` raises `McpProxyAdapterError` unless: `message` is a `Mapping`; `message["phase"] == "mcp"`; `message["event"]` is a `Mapping`; `direction` is `"request"` or `"response"`; `rpc` is a `Mapping`; `server` is a non-empty `str`.
- Request: raise unless `rpc["method"] == "tools/call"` and `rpc["params"]` is a `Mapping` with a non-empty `str` `name`. `tool_name = params["name"]`; argument source = `params["arguments"]`; `step_type=StepType.ACT`, `outcome=Outcome.OK`, `ended_at=None`.
- Response: `tool_name = event["tool_name"]` (raise if missing/not a non-empty `str`); `outcome=Outcome.ERROR` when `rpc.get("error")` is not `None` else `Outcome.OK`; response source = `rpc["error"]` when error else `rpc["result"]`; `step_type=StepType.OBSERVE`, `ended_at=event_time`.
- `session_id = str(event.get("session_id") or "unknown")`; `project = event["cwd"]` when a `str`; `trace_id = str(event.get("trace_id") or session_id)`; `span_id = f"mcp:{server}:{rpc['id']}"` when `rpc.get("id")` is not `None` and not a `bool`, else `None`.
- Timestamps: parse `event["timestamp"]` with `_parse_iso`; a malformed string raises `McpProxyAdapterError`; absent means `datetime.now(timezone.utc)`.
- Redaction: call `redact_mapping` on the argument/response source; collect kinds and emit `SecurityEvent(type=SecurityEventType.SECRET_DETECTED, emitter="agentwatch", tool=tool_name, evidence={"kinds": list(kinds)})` when non-empty. Reuse the `_arguments`-style capture helper (metadata-only unless `redaction` allows, mapping `PrivacyMode` → `RecordPrivacyMode`) from `claude_code.py`. Argument/response content is captured only when the source is a `Mapping`.
- `AgentIdentity(identity="unknown")`; `harness=HARNESS_ID`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_adapter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/adapters/mcp_proxy.py packages/python-sdk/tests/test_mcp_proxy_adapter.py
git commit -s -m "feat(adapters): MCP proxy adapter normalizes tools/call frames (M10 N1 #83)"
```

---

### Task 2: Publish the `mcp` daemon phase

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/protocol.py` (`FRAME_PHASES`)
- Modify: `packages/python-sdk/tests/test_protocol_contract.py`
- Modify: `docs/reference/daemon-protocol.md`

**Interfaces:**
- Produces: `protocol.FRAME_PHASES` contains `"mcp"` (additive).

- [ ] **Step 1: Extend the failing contract test**

In `test_daemon_frame_shapes_match_the_published_protocol`, add `"mcp"` to the asserted set and add:

```python
def test_mcp_phase_is_published() -> None:
    assert "mcp" in protocol.FRAME_PHASES
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_protocol_contract.py -v`
Expected: FAIL — `"mcp"` not in `FRAME_PHASES`.

- [ ] **Step 3: Add the phase and document it**

Add `"mcp",` to `protocol.FRAME_PHASES`. In `docs/reference/daemon-protocol.md`, add a `mcp` row to the Phases table: “MCP interposition proxy frame — `tools/call` request/response with `tool.server` attribution (M10 N1).”

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_protocol_contract.py tests/test_hook.py tests/test_daemon.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/protocol.py packages/python-sdk/tests/test_protocol_contract.py docs/reference/daemon-protocol.md
git commit -s -m "docs(protocol): publish the mcp daemon phase (M10 N1 #212)"
```

---

### Task 3: Register the adapter for conformance

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/adapters/__init__.py`
- Modify: `packages/python-sdk/tests/conformance_registry.py`
- Create: `packages/python-sdk/tests/fixtures/mcp-proxy/tools-call-request.json`, `.../tools-call-response.json`
- Modify: `docs/reference/adapter-conformance.md`

**Interfaces:**
- Consumes: `mcp_proxy` from Task 1.
- Produces: `mcp_proxy_spec() -> conformance.AdapterSpec`, registered so `test_all_shipped_adapters_are_registered` and `test_registered_shipped_adapters_conform` cover it.

- [ ] **Step 1: Add `mcp_proxy` to the shipped adapters**

In `adapters/__init__.py`, import `mcp_proxy` and add `"mcp_proxy"` to `__all__` (this makes the registry test fail until Step 2).

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_conformance_runner.py::test_all_shipped_adapters_are_registered -v`
Expected: FAIL — `mcp-proxy is shipped but not registered for conformance`.

- [ ] **Step 3: Write the fixtures and register the spec**

Create `tools-call-request.json`:

```json
{
  "message": {
    "phase": "mcp", "harness": "mcp-proxy",
    "event": {
      "server": "github", "session_id": "s-1", "direction": "request",
      "rpc": {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
              "params": {"name": "issue_get", "arguments": {"number": 3}}},
      "timestamp": "2026-01-02T03:04:05+00:00", "cwd": "/repo"
    }
  },
  "expected": [{
    "schema_version": "0.1.0", "session_id": "s-1", "agent": {"identity": "unknown"},
    "tool": {"name": "issue_get", "server": "github"}, "outcome": "ok",
    "started_at": "2026-01-02T03:04:05+00:00", "trace_id": "s-1",
    "span_id": "mcp:github:7", "harness": "mcp-proxy", "project": "/repo", "step_type": "act"
  }]
}
```

Create `tools-call-response.json` with the same event but `"direction": "response"`, `"tool_name": "issue_get"`, `"rpc": {"jsonrpc": "2.0", "id": 7, "result": {"ok": true}}`, `"timestamp": "2026-01-02T03:04:06+00:00"`, and `"expected"` equal to the request record plus `"ended_at": "2026-01-02T03:04:06+00:00"` and `"step_type": "observe"`.

In `conformance_registry.py`, add `mcp_proxy` to the import and:

```python
def mcp_proxy_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=mcp_proxy.HARNESS_ID,
        normalize=mcp_proxy.normalize,
        capabilities=mcp_proxy.CAPABILITIES,
        documented_gaps=mcp_proxy.DOCUMENTED_GAPS,
        error_cls=mcp_proxy.McpProxyAdapterError,
        fixtures_dir=FIXTURES / "mcp-proxy",
    )
```

Add `mcp_proxy_spec()` to `_shipped_specs()`. In `docs/reference/adapter-conformance.md`, name `mcp-proxy` in the registered-adapter list with its `mcp-tools` capability and `mcp-resources`/`mcp-prompts`/`mcp-sampling` gaps.

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_conformance_runner.py tests/test_conformance_packs.py tests/test_community_adapter.py -v`
Expected: PASS (including `fixtures-populated` and `fixture-replay`).

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/adapters/__init__.py packages/python-sdk/tests/conformance_registry.py packages/python-sdk/tests/fixtures/mcp-proxy docs/reference/adapter-conformance.md
git commit -s -m "test(conformance): register the MCP proxy adapter (M10 N1 #83)"
```

---

### Task 4: Route the `mcp` phase in the daemon

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/daemon.py`
- Test: `packages/python-sdk/tests/test_mcp_proxy_daemon.py`

**Interfaces:**
- Consumes: `mcp_proxy.normalize`, `McpProxyAdapterError` (Task 1); `protocol` phase (Task 2).
- Produces: `Daemon.handle_message` persists records for `phase == "mcp"` (dedup + chain reused).

- [ ] **Step 1: Write the failing test**

```python
# packages/python-sdk/tests/test_mcp_proxy_daemon.py
from __future__ import annotations

from pathlib import Path

from agentwatch.daemon import Daemon
from agentwatch.store import RecordStore

FRAME = {
    "phase": "mcp",
    "harness": "mcp-proxy",
    "event": {
        "server": "github",
        "session_id": "s-1",
        "direction": "request",
        "rpc": {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "issue_get", "arguments": {"number": 3}}},
        "timestamp": "2026-01-02T03:04:05+00:00",
    },
}


def test_daemon_persists_an_mcp_frame(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(socket_path=tmp_path / "d.sock", store=store, records_path=tmp_path / "records.jsonl")

    written = daemon.handle_message(FRAME)

    assert len(written) == 1
    record = store.records()[0]
    assert record.tool.name == "issue_get"
    assert record.tool.server == "github"
    assert store.verify().ok


def test_daemon_dedups_a_repeated_mcp_frame(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(socket_path=tmp_path / "d.sock", store=store, records_path=tmp_path / "records.jsonl")

    daemon.handle_message(FRAME)
    second = daemon.handle_message(FRAME)

    assert second == []
    assert len(store.records()) == 1


def test_daemon_quarantines_an_invalid_mcp_frame(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    daemon = Daemon(socket_path=tmp_path / "d.sock", store=store, records_path=tmp_path / "records.jsonl")

    bad = {**FRAME, "event": {**FRAME["event"], "direction": "sideways"}}
    written = daemon.handle_message(bad)

    assert written == []
    assert store.records() == []
    assert (tmp_path / "quarantine.jsonl").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_daemon.py -v`
Expected: FAIL — `mcp` frames yield no records (phase not handled).

- [ ] **Step 3: Implement the route**

In `daemon.py`, import `from agentwatch.adapters import mcp_proxy` and `McpProxyAdapterError`. In `handle_message`, after the `event` branch and before the Claude Code phase guard, add:

```python
if phase == "mcp":
    return self._handle_mcp(message, harness)
```

Add `_handle_mcp(self, message, harness)` that: calls `self.health.note_hook_fire(harness)`; normalizes via `mcp_proxy.normalize(message, redaction=self.redaction)`; on `(McpProxyAdapterError, ValueError, TypeError, KeyError)` quarantines `json.dumps(message, default=str)` with reason `"mcp-normalize-error"` and returns `[]`; otherwise applies the existing `self._seen` dedup and `self._append` loop (same as the tail of `handle_message`) and returns the written records. Do not run the Claude Code `_pending_pre` logic for `mcp` frames.

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_daemon.py tests/test_daemon.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/daemon.py packages/python-sdk/tests/test_mcp_proxy_daemon.py
git commit -s -m "feat(daemon): route mcp frames through the proxy adapter (M10 N1 #83)"
```

---

### Task 5: Proxy framing, pairing, and session helpers

**Files:**
- Create: `packages/python-sdk/src/agentwatch/mcp_proxy.py` (helpers only in this task)
- Test: `packages/python-sdk/tests/test_mcp_proxy_frames.py`

**Interfaces:**
- Produces:
  - `resolve_session_id(env: Mapping[str, str] | None = None) -> str`
  - `request_frame(server: str, session_id: str, rpc: Mapping[str, Any], *, timestamp: str | None = None, cwd: str | None = None) -> dict[str, Any]`
  - `response_frame(server: str, session_id: str, rpc: Mapping[str, Any], *, tool_name: str, timestamp: str | None = None, cwd: str | None = None) -> dict[str, Any]`
  - `is_tools_call_request(message: Any) -> bool`
  - `class Recorder` with `__init__(self, server: str, session_id: str, *, socket_path: str | None = None, cwd: str | None = None)`, `observe_from_harness(self, message: Any) -> None`, `observe_from_server(self, message: Any) -> None`, `flush_pending(self, reason: str = "server exited") -> None`.
- Consumes: `agentwatch.hook.send`, `agentwatch.spool.Spool`.

- [ ] **Step 1: Write the failing tests**

```python
# packages/python-sdk/tests/test_mcp_proxy_frames.py
from __future__ import annotations

import pytest

from agentwatch import mcp_proxy


def test_resolve_session_id_prefers_agentwatch_then_claude():
    assert mcp_proxy.resolve_session_id({"AGENTWATCH_SESSION_ID": "a", "CLAUDE_SESSION_ID": "b"}) == "a"
    assert mcp_proxy.resolve_session_id({"CLAUDE_SESSION_ID": "b"}) == "b"
    assert mcp_proxy.resolve_session_id({}).startswith("mcp-")


def test_request_frame_shape():
    frame = mcp_proxy.request_frame(
        "github", "s-1", {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}}
    )
    assert frame == {
        "phase": "mcp",
        "harness": "mcp-proxy",
        "event": {
            "server": "github",
            "session_id": "s-1",
            "direction": "request",
            "rpc": {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}},
        },
    }


def test_response_frame_carries_tool_name():
    frame = mcp_proxy.response_frame(
        "github", "s-1", {"jsonrpc": "2.0", "id": 7, "result": {}}, tool_name="issue_get"
    )
    assert frame["event"]["direction"] == "response"
    assert frame["event"]["tool_name"] == "issue_get"


def test_is_tools_call_request():
    assert mcp_proxy.is_tools_call_request({"method": "tools/call", "id": 1, "params": {"name": "x"}})
    assert not mcp_proxy.is_tools_call_request({"method": "initialize", "id": 1})
    assert not mcp_proxy.is_tools_call_request([{"method": "tools/call"}])  # batch: not a dict
    assert not mcp_proxy.is_tools_call_request({"method": "tools/call", "params": {}})  # no name


def test_recorder_pairs_request_and_response(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict] = []
    monkeypatch.setattr(mcp_proxy.hook, "send", lambda message, **_: sent.append(message) or True)
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "issue_get"}}
    )
    recorder.observe_from_server({"jsonrpc": "2.0", "id": 7, "result": {"ok": True}})

    assert [f["event"]["direction"] for f in sent] == ["request", "response"]
    assert sent[1]["event"]["tool_name"] == "issue_get"


def test_recorder_ignores_an_unpaired_response(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict] = []
    monkeypatch.setattr(mcp_proxy.hook, "send", lambda message, **_: sent.append(message) or True)
    recorder = mcp_proxy.Recorder("github", "s-1")

    recorder.observe_from_server({"jsonrpc": "2.0", "id": 99, "result": {}})

    assert sent == []


def test_flush_pending_records_an_error_for_an_unanswered_request(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict] = []
    monkeypatch.setattr(mcp_proxy.hook, "send", lambda message, **_: sent.append(message) or True)
    recorder = mcp_proxy.Recorder("github", "s-1")
    recorder.observe_from_harness(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "issue_get"}}
    )

    recorder.flush_pending("server exited")

    assert sent[-1]["event"]["direction"] == "response"
    assert sent[-1]["event"]["tool_name"] == "issue_get"
    assert sent[-1]["event"]["rpc"]["error"]["message"] == "server exited"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_frames.py -v`
Expected: FAIL — `ModuleNotFoundError: agentwatch.mcp_proxy`.

- [ ] **Step 3: Implement the helpers**

- `resolve_session_id`: `env` defaults to `os.environ`; return `AGENTWATCH_SESSION_ID`, else `CLAUDE_SESSION_ID`, else `f"mcp-{uuid.uuid4().hex[:12]}"`.
- `request_frame` / `response_frame`: build the documented frame; include `timestamp`/`cwd` in `event` only when not `None`.
- `is_tools_call_request`: `isinstance(message, Mapping)` and `message.get("method") == "tools/call"` and `isinstance(params, Mapping)` and non-empty `str` `params.get("name")`.
- `Recorder.observe_from_harness`: if `is_tools_call_request`, remember `rpc["id"] -> params["name"]` and emit `request_frame`. Otherwise ignore (relay-only).
- `Recorder.observe_from_server`: if the message is a `Mapping` whose `id` is in the remembered map, pop it and emit `response_frame(..., tool_name=...)`. Otherwise ignore (covers Review Focus 1 and 2).
- `Recorder.flush_pending(reason)`: for each still-remembered request id, emit `response_frame(..., tool_name=..., rpc={"jsonrpc": "2.0", "id": id, "error": {"code": -32000, "message": reason}})` and clear it. This is the transport-failure path: a server that exits mid-call still yields an `outcome=error` record.
- `Recorder._emit(frame)`: `hook.send(frame, socket_path=self.socket_path)`; when it returns `False`, append to `Spool((self.socket_path or hook.default_spool_path()) + ".spool")` — never raise.

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_frames.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/mcp_proxy.py packages/python-sdk/tests/test_mcp_proxy_frames.py
git commit -s -m "feat(mcp): proxy framing, pairing, and session helpers (M10 N1 #83)"
```

---

### Task 6: stdio relay + `run_stdio` + `main`

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/mcp_proxy.py`
- Create: `packages/python-sdk/tests/fixtures/mcp/echo_server.py`
- Test: `packages/python-sdk/tests/test_mcp_proxy_stdio.py`

**Interfaces:**
- Produces: `run_stdio(server_name: str, command: Sequence[str], *, socket_path: str | None = None, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None, env: Mapping[str, str] | None = None) -> int`; `main(argv: Sequence[str] | None = None) -> int`.
- Consumes: helpers from Task 5.

- [ ] **Step 1: Write the fake MCP server and the failing tests**

`tests/fixtures/mcp/echo_server.py` — a minimal stdio server:

```python
"""Tiny MCP-ish stdio server for proxy tests (echoes tools/call results)."""
import json
import sys


def main() -> int:
    for line in sys.stdin.buffer:
        try:
            message = json.loads(line)
        except ValueError:
            sys.stdout.buffer.write(line)  # echo garbage unchanged
            sys.stdout.buffer.flush()
            continue
        if not isinstance(message, dict):
            continue
        if message.get("method") == "tools/call":
            reply = {"jsonrpc": "2.0", "id": message.get("id"),
                     "result": {"echo": message.get("params", {}).get("name")}}
        else:
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}
        sys.stdout.buffer.write(json.dumps(reply).encode() + b"\n")
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Tests — feed requests through injectable `BytesIO` streams, capture emitted frames by monkeypatching `mcp_proxy.hook.send`:

```python
# packages/python-sdk/tests/test_mcp_proxy_stdio.py
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from agentwatch import mcp_proxy

ECHO = Path(__file__).resolve().parent / "fixtures" / "mcp" / "echo_server.py"


def _run(payload: bytes, monkeypatch, tmp_path, frames: list[dict]) -> bytes:
    monkeypatch.setattr(mcp_proxy.hook, "send", lambda message, **_: frames.append(message) or True)
    stdin, stdout = io.BytesIO(payload), io.BytesIO()
    mcp_proxy.run_stdio(
        "echo", [sys.executable, str(ECHO)], socket_path=str(tmp_path / "d.sock"),
        stdin=stdin, stdout=stdout, env={},
    )
    return stdout.getvalue()


def test_records_request_and_response(monkeypatch, tmp_path):
    frames: list[dict] = []
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}\n'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out)["result"] == {"echo": "echo"}
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]


def test_forwards_lines_unchanged(monkeypatch, tmp_path):
    frames: list[dict] = []
    request = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert frames == []  # non-tools/call not recorded


def test_malformed_line_is_forwarded_but_not_recorded(monkeypatch, tmp_path):
    frames: list[dict] = []
    out = _run(b"not json\n", monkeypatch, tmp_path, frames)
    assert out == b"not json\n"
    assert frames == []


def test_line_without_trailing_newline_is_forwarded(monkeypatch, tmp_path):
    frames: list[dict] = []
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}'
    out = _run(request, monkeypatch, tmp_path, frames)
    assert json.loads(out)["result"] == {"echo": "echo"}
    assert len(frames) == 2


def test_server_exit_without_response_records_an_error(monkeypatch, tmp_path):
    frames: list[dict] = []
    monkeypatch.setattr(mcp_proxy.hook, "send", lambda message, **_: frames.append(message) or True)
    request = b'{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"echo"}}\n'
    mcp_proxy.run_stdio(
        "echo", [sys.executable, "-c", "import sys; sys.stdin.readline()"],
        socket_path=str(tmp_path / "d.sock"),
        stdin=io.BytesIO(request), stdout=io.BytesIO(), env={},
    )
    assert [f["event"]["direction"] for f in frames] == ["request", "response"]
    assert frames[1]["event"]["rpc"]["error"]["message"] == "server exited"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_stdio.py -v`
Expected: FAIL — `run_stdio` is not defined.

- [ ] **Step 3: Implement `run_stdio` and `main`**

- `run_stdio`: spawn `command` with `subprocess.Popen(command, stdin=PIPE, stdout=PIPE, env={**os.environ, **(env or {})})`; wrap `child.stdin`/`child.stdout` as binary. Build `Recorder(server_name, resolve_session_id(env), socket_path=socket_path, cwd=os.getcwd())`.
  - One thread reads harness `stdin` line by line; for each line it writes the bytes to `child.stdin` (flush), then parses it (JSON, contained on failure) and calls `recorder.observe_from_harness`. On EOF it closes `child.stdin`.
  - The main thread reads `child.stdout` line by line; for each line it writes the bytes to `stdout` (flush), then parses and calls `recorder.observe_from_server`. On EOF it stops.
  - Join the thread; `child.wait()`; then `recorder.flush_pending("server exited")` so an unanswered in-flight request is recorded as an error; return `child.returncode if child.returncode is not None else 0`.
  - Reading a final line without a trailing newline must still forward and parse it (iterate the binary stream, which yields the trailing bytes); a top-level JSON array (batch) is not a `Mapping` and is ignored by the recorder (Review Focus 3).
- `main`: `argparse.ArgumentParser(prog="agentwatch-mcp-proxy")` with `--server` (required), `--socket` (default `None`), and `command` as `nargs=argparse.REMAINDER`. Strip a leading `"--"` from `command`; when empty, print `agentwatch-mcp-proxy: requires -- <server command> [args...]` to `stderr` and return `2`; otherwise return `run_stdio(args.server, command, socket_path=args.socket)`. Add `if __name__ == "__main__": raise SystemExit(main())`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_mcp_proxy_stdio.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/src/agentwatch/mcp_proxy.py packages/python-sdk/tests/fixtures/mcp/echo_server.py packages/python-sdk/tests/test_mcp_proxy_stdio.py
git commit -s -m "feat(mcp): stdio relay records tools/call both directions (M10 N1 #83)"
```

---

### Task 7: Console entry point + `agentwatch mcp-proxy` subcommand

**Files:**
- Modify: `packages/python-sdk/pyproject.toml` (`[project.scripts]`)
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Modify: `packages/python-sdk/tests/test_packaging_metadata.py`
- Test: `packages/python-sdk/tests/test_cli_mcp_proxy.py`

**Interfaces:**
- Consumes: `mcp_proxy.main` (Task 6).
- Produces: `agentwatch-mcp-proxy` console script; `agentwatch mcp-proxy --server NAME -- <command> [args…]`.

- [ ] **Step 1: Write the failing tests**

Add to `test_packaging_metadata.py`:

```python
def test_mcp_proxy_console_script_is_declared() -> None:
    scripts = _metadata()["project"].get("scripts", {})
    assert scripts.get("agentwatch-mcp-proxy") == "agentwatch.mcp_proxy:main"
```

Create `tests/test_cli_mcp_proxy.py`:

```python
from __future__ import annotations

import io
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

    def fake_run_stdio(server, command, **kwargs):
        captured["server"] = server
        captured["command"] = list(command)
        return 0

    monkeypatch.setattr(mcp_proxy, "run_stdio", fake_run_stdio)
    rc = main(["mcp-proxy", "--server", "echo", "--", sys.executable, str(ECHO)])

    assert rc == 0
    assert captured == {"server": "echo", "command": [sys.executable, str(ECHO)]}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/python-sdk && python -m pytest tests/test_packaging_metadata.py::test_mcp_proxy_console_script_is_declared tests/test_cli_mcp_proxy.py -v`
Expected: FAIL — script not declared; `mcp-proxy` is an invalid subcommand.

- [ ] **Step 3: Wire the entry point and subcommand**

Add `agentwatch-mcp-proxy = "agentwatch.mcp_proxy:main"` to `[project.scripts]`. In `cli/main.py`, add a `mcp-proxy` subparser with `--server` (required), `--socket` (default `None`), and `command` (`nargs=argparse.REMAINDER`); add `_run_mcp_proxy(args)` that imports `run_stdio`, strips a leading `"--"` from `command`, returns `_EXIT_USAGE_ERROR` (2) with a stderr message when empty, else delegates; dispatch it in `main()`; add `"mcp-proxy"` to `_COMMANDS_FOR_COMPLETION`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/python-sdk && python -m pytest tests/test_cli_mcp_proxy.py tests/test_packaging_metadata.py tests/test_cli.py tests/test_cli_init.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python-sdk/pyproject.toml packages/python-sdk/src/agentwatch/cli/main.py packages/python-sdk/tests/test_packaging_metadata.py packages/python-sdk/tests/test_cli_mcp_proxy.py
git commit -s -m "feat(cli): agentwatch mcp-proxy + console entry point (M10 N1 #83)"
```

---

### Task 8: Milestone docs + full verification

**Files:**
- Modify: `docs/reference/known-limitations.md`
- Modify: `docs/reference/compatibility.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`
- Modify: `docs/plans/README.md` (link this plan if the index lists plans)

- [ ] **Step 1: Update the docs**

- `known-limitations.md`: note MCP resources/prompts/sampling are relayed but not recorded; HTTP/SSE and `init --mcp-proxy` land in Plan B.
- `compatibility.md`: add an MCP-proxy row (Claude Code and any MCP-speaking harness; stdio in Plan A, HTTP/SSE Plan B), with the declared gaps.
- `CHANGELOG.md`: an Unreleased entry for the MCP proxy adapter + stdio relay (`phase: mcp`, #83/#212).
- WBS Part 6 + index: mark 10.5/10.N1 **partial (Plan A: adapter + stdio + daemon + conformance); HTTP/SSE + install/restore in Plan B**, and link `docs/design/mcp-proxy-design.md` and this plan.

- [ ] **Step 2: Run the full gate for the package**

Run: `cd packages/python-sdk && python -m pytest --cov --cov-report=term --cov-fail-under=95`
Expected: PASS, coverage ≥ 95%.

- [ ] **Step 3: Lint and type-check**

Run: `cd packages/python-sdk && ruff check . && mypy --strict .`
Expected: no output (clean).

- [ ] **Step 4: Repo guard**

Run: `python -m pytest tests`
Expected: PASS (docs link-check, namespace guard).

- [ ] **Step 5: Commit**

```bash
git add docs/reference/known-limitations.md docs/reference/compatibility.md CHANGELOG.md docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md docs/wbs/v0.1.0/wbs-v0.1.0-index.md docs/plans/README.md
git commit -s -m "docs(m10): record MCP proxy Plan A progress (#83 #212)"
```
