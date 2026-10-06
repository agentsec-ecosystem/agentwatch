"""Detectors stay compatible with the real downloaded traces (M26 DET-2, #321).

The testkit corpus holds real, licensed captures: Claude Code transcripts,
Codex rollouts, and Cursor session-tracer traces. Every rule detector must run
over runs derived from them without raising and must return a well-formed
verdict (``None`` or a typed ``Anomaly``) — the detectors must not depend on
synthetic-only span shapes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("agentwatch")

from agentwatch import transcript  # noqa: E402
from analytics.detectors import create_all_detectors  # noqa: E402
from analytics.models import RunSummary, SpanNode  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
KIT = REPO / "packages" / "python-sdk" / "tests" / "testkit"


def _tool_spans(names: list[str]) -> list[SpanNode]:
    children = [
        SpanNode(
            span_id=f"s{i}",
            trace_id="real-trace",
            parent_span_id="root",
            operation_name="execute_tool",
            attributes={"gen_ai.tool.name": name},
        )
        for i, name in enumerate(names)
    ]
    return [
        SpanNode(
            span_id="root",
            trace_id="real-trace",
            operation_name="invoke_agent",
            child_spans=children,
        )
    ]


def _assert_detectors_ok(summary: RunSummary, spans: list[SpanNode]) -> None:
    detectors = create_all_detectors()

    async def run() -> None:
        for detector in detectors:
            result = await detector.detect_async(summary, spans, pool=None)
            assert result is None or isinstance(result.anomaly_type, str)

    asyncio.run(run())


def _run(run_id: str, names: list[str]) -> None:
    summary = RunSummary(
        run_id=run_id, agent_name="real-trace", total_tool_calls=len(names)
    )
    _assert_detectors_ok(summary, _tool_spans(names))


def test_detectors_accept_real_claude_code_transcripts() -> None:
    files = sorted((KIT / "claude-code").rglob("rollouts/*.jsonl"))
    assert files, "Claude Code testkit corpus is missing"

    for path in files:
        coverage = transcript.extract_tool_calls(path)
        # The ordered sequence is the real captured tool-call order.
        _run(path.stem, list(coverage.sequence))


def test_detectors_accept_real_cursor_session_traces() -> None:
    files = sorted((KIT / "cursor" / "cursor-session-tracer" / "traces").glob("*.json"))
    assert files, "Cursor tracer corpus is missing"

    for path in files:
        trace = json.loads(path.read_text(encoding="utf-8"))
        names: list[str] = []
        for event in trace.get("events", []):
            names.extend(["Read"] * len(event.get("files_read", [])))
            kind = event.get("type")
            if kind == "file_create":
                names.append("Write")
            elif kind == "file_modify":
                names.append("Edit")
            elif kind == "file_delete":
                names.append("Delete")
        _run(path.stem, names)


def test_detectors_tolerate_real_codex_rollouts() -> None:
    files = sorted((KIT / "codex").rglob("rollouts/*.jsonl"))
    assert files, "Codex testkit corpus is missing"

    for path in files:
        # Rollouts carry no tool-call taxonomy we can classify; the contract is
        # that a real harness run with no recognized tool calls is tolerated.
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
        _run(path.stem, [])
