"""Deterministic fake-harness emitters (M10 N3 #214).

Test utilities only (never production): one small emitter per supported platform
producing realistic native-event streams — plus malformed, out-of-order,
duplicate, and clock-skew variants — so daemon/pipeline tests exercise the
long-running paths (pairing, dedup, gaps, quarantine) without a real harness,
auth, or network. Synthetic data only.

The emitter's event shapes must stay in lockstep with the adapters; the version
matrix (N4) and conformance runner flag drift.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from typing import Any

# Native phases each platform's adapter accepts, in a realistic order.
PLATFORM_PHASES: dict[str, tuple[str, ...]] = {
    "claude-code": ("pre", "post"),
    "cursor": (
        "beforeShellExecution",
        "afterShellExecution",
        "beforeReadFile",
        "afterFileEdit",
    ),
    "codex-cli": ("exec_begin", "exec_end", "patch_apply"),
    "gemini-cli": ("tool_call", "tool_result", "session_start", "session_end"),
    "mcp-proxy": ("request", "response"),
}

PLATFORMS: tuple[str, ...] = tuple(PLATFORM_PHASES)


def _timestamp(index: int) -> str:
    return f"2026-01-02T03:04:{index % 60:02d}+00:00"


def _event(platform: str, phase: str, index: int) -> dict[str, Any]:
    session = f"sess-{platform}"
    call_id = f"{platform}-call-{index}"
    ts = _timestamp(index)
    if platform == "claude-code":
        event: dict[str, Any] = {
            "session_id": session,
            "call_id": call_id,
            "tool_name": "Bash",
            "timestamp": ts,
        }
        if phase == "pre":
            event["tool_input"] = {"command": f"echo {index}"}
        else:
            event["tool_response"] = {"content": f"ok {index}"}
            event["started_at"] = ts
        return {"phase": phase, "harness": platform, "event": event}
    if platform == "cursor":
        tool = "Shell" if "Shell" in phase else "Edit"
        return {
            "phase": phase,
            "harness": platform,
            "event": {"session_id": session, "call_id": call_id, "timestamp": ts, "tool": tool},
        }
    if platform == "codex-cli":
        event = {"session_id": session, "call_id": call_id, "timestamp": ts}
        if phase == "exec_end":
            event["exit_code"] = 0
        if phase == "patch_apply":
            event["success"] = True
        return {"phase": phase, "harness": platform, "event": event}
    if platform == "gemini-cli":
        event = {"session_id": session, "call_id": call_id, "timestamp": ts}
        if phase in ("tool_call", "tool_result"):
            event["tool"] = "read_file"
        return {"phase": phase, "harness": platform, "event": event}
    # mcp-proxy
    if phase == "request":
        rpc: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": index,
            "method": "tools/call",
            "params": {"name": "issue_get"},
        }
        return {
            "phase": "mcp",
            "harness": "mcp-proxy",
            "event": {
                "server": "github",
                "session_id": session,
                "direction": "request",
                "call_id": call_id,
                "rpc": rpc,
            },
        }
    return {
        "phase": "mcp",
        "harness": "mcp-proxy",
        "event": {
            "server": "github",
            "session_id": session,
            "direction": "response",
            "call_id": call_id,
            "tool_name": "issue_get",
            "rpc": {"jsonrpc": "2.0", "id": index, "result": {"ok": True}},
        },
    }


def realistic_stream(
    platform: str, *, count: int = 8, seed: int = 0
) -> Iterator[dict[str, Any]]:
    """Yield a deterministic, valid native-event stream for ``platform``."""
    if platform not in PLATFORM_PHASES:
        raise KeyError(f"no emitter for platform {platform!r}")
    rng = random.Random(seed)
    phases = PLATFORM_PHASES[platform]
    for index in range(count):
        # ``rng`` keeps the signature stable for future jitter without breaking
        # determinism today.
        rng.random()
        yield _event(platform, phases[index % len(phases)], index)


def out_of_order_stream(platform: str, *, count: int = 6, seed: int = 0) -> Iterator[Any]:
    """Yield a valid stream in reverse order (responses before their requests)."""
    return iter(list(realistic_stream(platform, count=count, seed=seed))[::-1])


def duplicate_stream(platform: str, *, count: int = 4, seed: int = 0) -> Iterator[Any]:
    """Yield every valid event twice (dedup exercise)."""
    for event in realistic_stream(platform, count=count, seed=seed):
        yield event
        yield dict(event)


def malformed_stream() -> Iterator[Any]:
    """Yield frames that no adapter can normalize (quarantine exercise)."""
    yield "not-a-mapping"
    yield {"phase": "bogus", "event": {"session_id": "s"}}
    yield {"phase": "pre"}
    yield {"phase": "pre", "event": "not-an-object"}


def clock_skew_stream() -> Iterator[Any]:
    """Yield a valid pair whose end precedes its start (B5 exercise)."""
    yield {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-skew",
            "call_id": "skew-1",
            "tool_name": "Bash",
            "tool_input": {"command": "x"},
            "timestamp": "2030-01-01T00:00:00+00:00",
        },
    }
    yield {
        "phase": "post",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-skew",
            "call_id": "skew-1",
            "tool_name": "Bash",
            "tool_response": {"content": "ok"},
            "started_at": "2030-01-01T00:00:00+00:00",
            "timestamp": "2020-01-01T00:00:00+00:00",
        },
    }
