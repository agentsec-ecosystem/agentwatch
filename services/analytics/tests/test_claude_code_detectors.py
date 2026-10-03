"""Tests for the Claude Code detector starter pack (M6 addition L1)."""

from __future__ import annotations

from typing import Any

from analytics.detectors import create_all_detectors
from analytics.detectors.claude_code import (
    DeniedClusterDetector,
    NetworkToolDetector,
    WriteStormDetector,
)
from analytics.models import RunSummary, SpanNode


def _summary() -> RunSummary:
    return RunSummary(run_id="run-1", agent_name="test-agent")


def _root(children: list[SpanNode]) -> list[SpanNode]:
    return [
        SpanNode(
            span_id="root",
            trace_id="t",
            operation_name="invoke_agent",
            child_spans=children,
        )
    ]


def _tool(index: int, name: str, **kwargs: Any) -> SpanNode:
    status: str | None = kwargs.pop("status", None)
    outcome: str | None = kwargs.pop("outcome", None)
    attributes: dict[str, object] = {"gen_ai.tool.name": name}
    if outcome is not None:
        attributes["agentwatch.outcome"] = outcome
    return SpanNode(
        span_id=f"s{index}",
        trace_id="t",
        operation_name="execute_tool",
        parent_span_id="root",
        status=status,
        attributes=attributes,
    )


def test_write_storm_fires_on_many_writes() -> None:
    spans = _root([_tool(i, "Write") for i in range(8)])

    anomaly = WriteStormDetector(threshold=8).detect(_summary(), spans)

    assert anomaly is not None
    assert anomaly.anomaly_type == "write-storm"
    assert (anomaly.evidence or {})["count"] == 8


def test_write_storm_is_silent_below_threshold() -> None:
    spans = _root([_tool(i, "Write") for i in range(3)])

    assert WriteStormDetector(threshold=8).detect(_summary(), spans) is None


def test_denied_cluster_fires_on_error_status() -> None:
    spans = _root([_tool(i, "Bash", status="error") for i in range(3)])

    anomaly = DeniedClusterDetector(threshold=3).detect(_summary(), spans)

    assert anomaly is not None
    assert anomaly.anomaly_type == "denied-cluster"


def test_denied_cluster_counts_marked_denied() -> None:
    spans = _root([_tool(i, "Bash", outcome="denied") for i in range(2)])

    assert DeniedClusterDetector(threshold=2).detect(_summary(), spans) is not None


def test_network_tool_flags_usage() -> None:
    spans = _root([_tool(0, "curl")])

    anomaly = NetworkToolDetector().detect(_summary(), spans)

    assert anomaly is not None
    assert anomaly.severity == "info"


def test_network_tool_allowlist_silences() -> None:
    spans = _root([_tool(0, "curl")])

    assert NetworkToolDetector(allowlist=("curl",)).detect(_summary(), spans) is None


def test_registry_includes_the_claude_code_detectors() -> None:
    types = {detector.anomaly_type for detector in create_all_detectors()}

    assert {"write-storm", "denied-cluster", "network-tool"} <= types
