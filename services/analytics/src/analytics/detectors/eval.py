"""Offline detector-eval harness (M25 DET-1, PRD 43).

One command, offline, deterministic: drives the **real** analytics detectors over a
versioned corpus and reports per-detector precision/recall. The harness judges
detectors; detectors judge nothing, and the LLM stays out of the trust path. The
corpus format is the Q6 ``expected-verdicts`` pattern (see design/detector-evaluation.md).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analytics.detectors import create_all_detectors
from analytics.detectors.base import BaseDetector
from analytics.models import RunSummary, SpanNode

CORPUS_VERSION_KEY = "version"


@dataclass(frozen=True)
class DetectorCase:
    """One corpus case: a run summary + span tree and the detectors expected to fire."""

    id: str
    summary: RunSummary
    spans: list[SpanNode]
    expected: frozenset[str]


@dataclass(frozen=True)
class Outcome:
    """One (case, detector) observation."""

    case_id: str
    detector: str
    fired: bool
    expected: bool


@dataclass(frozen=True)
class EvalReport:
    """Per-detector precision/recall over a corpus; deterministic ordering."""

    outcomes: tuple[Outcome, ...]

    def detectors(self) -> tuple[str, ...]:
        return tuple(sorted({outcome.detector for outcome in self.outcomes}))

    def _rows(self, detector: str) -> list[Outcome]:
        return [outcome for outcome in self.outcomes if outcome.detector == detector]

    def precision(self, detector: str) -> float:
        rows = self._rows(detector)
        tp = sum(outcome.fired and outcome.expected for outcome in rows)
        fp = sum(outcome.fired and not outcome.expected for outcome in rows)
        return tp / (tp + fp) if (tp + fp) else 0.0

    def recall(self, detector: str) -> float:
        rows = self._rows(detector)
        tp = sum(outcome.fired and outcome.expected for outcome in rows)
        fn = sum(not outcome.fired and outcome.expected for outcome in rows)
        return tp / (tp + fn) if (tp + fn) else 0.0


def _fires(detector: BaseDetector, summary: RunSummary, spans: list[SpanNode]) -> bool:
    result = asyncio.run(detector.detect_async(summary, spans, None))
    return result is not None


def run_eval(
    cases: list[DetectorCase], *, detectors: list[BaseDetector] | None = None
) -> EvalReport:
    """Run every detector over every case; deterministic and offline."""
    active = list(detectors) if detectors is not None else create_all_detectors()
    outcomes: list[Outcome] = []
    for case in cases:
        for detector in active:
            name = detector.anomaly_type
            outcomes.append(
                Outcome(
                    case_id=case.id,
                    detector=name,
                    fired=_fires(detector, case.summary, case.spans),
                    expected=name in case.expected,
                )
            )
    return EvalReport(tuple(outcomes))


def _tool_spans(tool_names: list[str]) -> list[SpanNode]:
    children = [
        SpanNode(
            span_id=f"s{index}",
            trace_id="corpus",
            parent_span_id="root",
            operation_name="execute_tool",
            attributes={"gen_ai.tool.name": name},
        )
        for index, name in enumerate(tool_names)
    ]
    return [
        SpanNode(
            span_id="root",
            trace_id="corpus",
            operation_name="invoke_agent",
            child_spans=children,
        )
    ]


def _case_from_spec(spec: dict[str, Any]) -> DetectorCase:
    tools = [str(name) for name in spec.get("tools", [])]
    summary = RunSummary(
        run_id=str(spec["id"]),
        agent_name=str(spec.get("agent_name", "corpus")),
        agent_version=str(spec.get("agent_version", "v1")),
    )
    return DetectorCase(
        id=str(spec["id"]),
        summary=summary,
        spans=_tool_spans(tools),
        expected=frozenset(str(name) for name in spec.get("expect", [])),
    )


def load_corpus(path: Path | str) -> list[DetectorCase]:
    """Load a case manifest (``{version, cases:[{id, tools, expect}]}``)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [_case_from_spec(spec) for spec in data.get("cases", [])]


__all__ = [
    "CORPUS_VERSION_KEY",
    "DetectorCase",
    "EvalReport",
    "Outcome",
    "load_corpus",
    "run_eval",
]