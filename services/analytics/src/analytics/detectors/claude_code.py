"""Claude Code hook-record detectors (M6 addition L1).

Signal-only detectors for shapes common in Claude Code hook traces:

- ``write-storm``: many file-modifying tool calls in one run.
- ``denied-cluster``: a cluster of denied/error tool calls.
- ``network-tool``: network-capable tools used (flag for review).

Observability only — these are signals with evidence, never enforcement
(PRD 14/18). Each reads its threshold from the constructor so the registry can
instantiate it without arguments.
"""

from __future__ import annotations

from analytics.detectors.base import BaseDetector
from analytics.models import Anomaly, RunSummary, SpanNode

_FILE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
_NETWORK_TOOLS = frozenset({"curl", "wget", "http", "fetch", "webfetch", "WebFetch"})


def _tool_name(span: SpanNode) -> str:
    return str(span.attributes.get("gen_ai.tool.name", ""))


class WriteStormDetector(BaseDetector):
    """Flag runs with many file-modifying tool calls in a row."""

    anomaly_type = "write-storm"

    def __init__(self, threshold: int = 8) -> None:
        self.threshold = threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        writes = [s for s in self._walk_tool_spans(spans) if _tool_name(s) in _FILE_WRITE_TOOLS]
        if len(writes) < self.threshold:
            return None
        tools = sorted({_tool_name(s) for s in writes})
        return self._build_anomaly(
            summary,
            self._severity(len(writes), self.threshold),
            f"file-write storm: {len(writes)} write tools (threshold {self.threshold})",
            {"count": len(writes), "threshold": self.threshold, "tools": tools},
        )


class DeniedClusterDetector(BaseDetector):
    """Flag runs with a cluster of denied or errored tool calls."""

    anomaly_type = "denied-cluster"

    def __init__(self, threshold: int = 3) -> None:
        self.threshold = threshold

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        denied = [
            span
            for span in self._walk_tool_spans(spans)
            if str(span.attributes.get("agentwatch.outcome", "")).lower() == "denied"
            or (span.status or "").lower() == "error"
        ]
        if len(denied) < self.threshold:
            return None
        return self._build_anomaly(
            summary,
            self._severity(len(denied), self.threshold),
            f"denied/error cluster: {len(denied)} calls (threshold {self.threshold})",
            {"count": len(denied), "threshold": self.threshold},
        )


class NetworkToolDetector(BaseDetector):
    """Flag runs that used network-capable tools (for review)."""

    anomaly_type = "network-tool"

    def __init__(self, allowlist: tuple[str, ...] = ()) -> None:
        self.allowlist = frozenset(allowlist)

    def detect(self, summary: RunSummary, spans: list[SpanNode]) -> Anomaly | None:
        hits = [
            span
            for span in self._walk_tool_spans(spans)
            if _tool_name(span) in _NETWORK_TOOLS and _tool_name(span) not in self.allowlist
        ]
        if not hits:
            return None
        tools = sorted({_tool_name(s) for s in hits})
        return self._build_anomaly(
            summary,
            "info",
            f"network-capable tools used: {', '.join(tools)}",
            {"count": len(hits), "tools": tools},
        )
