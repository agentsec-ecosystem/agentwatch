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

from analytics.detectors import create_all_detectors, create_llm_detectors
from analytics.detectors.base import BaseDetector
from analytics.detectors.pool import ScriptedPool
from analytics.llm_client import LLMClient
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


async def _eval_cases(
    cases: list[DetectorCase], active: list[BaseDetector]
) -> list[Outcome]:
    """Run every detector over every case inside one event loop.

    A single loop matters for the LLM detectors (DET-4): an async HTTP client is
    bound to the loop that first used it, so per-call ``asyncio.run`` would break
    it after the first call.
    """
    outcomes: list[Outcome] = []
    for case in cases:
        for detector in active:
            result = await detector.detect_async(case.summary, case.spans, None)
            outcomes.append(
                Outcome(
                    case_id=case.id,
                    detector=detector.anomaly_type,
                    fired=result is not None,
                    expected=detector.anomaly_type in case.expected,
                )
            )
    return outcomes


def run_eval(
    cases: list[DetectorCase],
    *,
    detectors: list[BaseDetector] | None = None,
    llm_client: LLMClient | None = None,
) -> EvalReport:
    """Run every detector over every case; deterministic and offline.

    Pass ``llm_client`` to include the 6 LLM-augmented detectors (DET-4) on the
    same harness — local-model-first, and strictly additive: the rule-based
    detectors run unchanged, and an unavailable model degrades them to no-op.
    """
    if detectors is not None:
        active = list(detectors)
    else:
        active = create_all_detectors()
        if llm_client is not None:
            active = active + create_llm_detectors(llm_client)
    return EvalReport(tuple(asyncio.run(_eval_cases(cases, active))))


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


# ---------------------------------------------------------------------------
# Public corpus v1 (M26 COR-1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublicCase:
    """One published corpus case: a run + spans + the detector that should fire."""

    id: str
    detector: str
    detector_kwargs: dict[str, Any]
    expect_fire: bool
    severity: str | None
    source: str
    dimension: str | None
    summary: RunSummary
    spans: list[SpanNode]
    pool: dict[str, Any] | None = None


@dataclass(frozen=True)
class PublicCorpus:
    """A versioned, machine-checkable public detector corpus."""

    schema: str
    version: str
    sources: tuple[str, ...]
    cases: tuple[PublicCase, ...]


@dataclass(frozen=True)
class CaseResult:
    """The machine-checkable verdict for one public-corpus case."""

    id: str
    detector: str
    fired: bool
    expected: bool
    severity_ok: bool
    ok: bool


def load_public_corpus(path: Path | str) -> PublicCorpus:
    """Load the public corpus (``{schema, version, sources, cases}``).

    Cases carry a serialized ``RunSummary`` + spawn tree, the detector that
    should fire, and a scripted pool for baseline detectors.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = tuple(
        PublicCase(
            id=str(spec["id"]),
            detector=str(spec["detector"]),
            detector_kwargs=dict(spec.get("detector_kwargs", {})),
            expect_fire=bool(spec["expect_fire"]),
            severity=spec.get("severity"),
            source=str(spec.get("source", "unknown")),
            dimension=spec.get("dimension"),
            summary=RunSummary.model_validate(spec["summary"]),
            spans=[SpanNode.model_validate(span) for span in spec.get("spans", [])],
            pool=spec.get("pool"),
        )
        for spec in data.get("cases", [])
    )
    return PublicCorpus(
        schema=str(data.get("schema", "")),
        version=str(data.get("version", "")),
        sources=tuple(str(source) for source in data.get("sources", [])),
        cases=cases,
    )


def detector_classes() -> dict[str, type[BaseDetector]]:
    """Rule-detector name -> class (LLM detectors are not included)."""
    return {detector.anomaly_type: type(detector) for detector in create_all_detectors()}


async def _check_case(case: PublicCase, classes: dict[str, type[BaseDetector]]) -> CaseResult:
    cls = classes.get(case.detector)
    if cls is None:
        return CaseResult(case.id, case.detector, False, case.expect_fire, False, False)
    detector = cls(**case.detector_kwargs)
    pool = ScriptedPool(case.pool) if case.pool is not None else None
    anomaly = await detector.detect_async(case.summary, case.spans, pool=pool)
    fired = anomaly is not None
    severity_ok = (not case.expect_fire) or case.severity is None or (
        anomaly is not None and anomaly.severity == case.severity
    )
    fire_ok = fired == case.expect_fire
    type_ok = (not fired) or (anomaly is not None and anomaly.anomaly_type == detector.anomaly_type)
    return CaseResult(
        id=case.id,
        detector=case.detector,
        fired=fired,
        expected=case.expect_fire,
        severity_ok=severity_ok,
        ok=fire_ok and severity_ok and type_ok,
    )


def check_public_corpus(corpus: PublicCorpus) -> tuple[CaseResult, ...]:
    """Run every case and return its machine-checkable verdict (offline)."""
    classes = detector_classes()
    return tuple(asyncio.run(_check_case(case, classes)) for case in corpus.cases)


__all__ = [
    "CORPUS_VERSION_KEY",
    "CaseResult",
    "DetectorCase",
    "EvalReport",
    "Outcome",
    "PublicCase",
    "PublicCorpus",
    "check_public_corpus",
    "detector_classes",
    "load_corpus",
    "load_public_corpus",
    "run_eval",
]