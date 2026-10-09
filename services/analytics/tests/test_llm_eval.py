"""LLM detectors on the shared eval harness (M27 DET-4 #343).

The 6 LLM-augmented detectors run through the same offline harness as the rule
detectors — local-model-first, strictly additive, and never in the deterministic
trust path. A scripted local client makes the evaluation deterministic in CI; a
real local model publishes the numbers (see design/detector-evaluation.md).
"""

from __future__ import annotations

from typing import Any, cast

from analytics.detectors import create_all_detectors, create_llm_detectors
from analytics.detectors.eval import DetectorCase, run_eval
from analytics.llm_client import LLMClient
from analytics.models import RunSummary, SpanNode

LLM_NAMES = {
    "output_drift",
    "semantic_loop",
    "hallucination",
    "goal_drift",
    "quality_degradation",
    "confusion_pattern",
}


class _StubClient:
    """A deterministic stand-in for a local model endpoint."""

    last_cache_hit = False

    def __init__(self, reply: str | None = None) -> None:
        self._reply = reply

    async def chat(self, *_: Any, **__: Any) -> str | None:
        return self._reply

    async def embed(self, *_: Any, **__: Any) -> None:
        return None


def _stub(reply: str | None = None) -> LLMClient:
    """A local-client stand-in, typed as the real client it duck-types."""
    return cast(LLMClient, _StubClient(reply))


def _case() -> DetectorCase:
    summary = RunSummary(run_id="c1", agent_name="agent", agent_version="v1")
    spans = [
        SpanNode(
            span_id="s1",
            trace_id="t1",
            operation_name="invoke_agent",
            attributes={"gen_ai.response.content": "the same output"},
        )
    ]
    return DetectorCase(
        id="c1", summary=summary, spans=spans, expected=frozenset({"semantic_loop"})
    )


def test_llm_detectors_are_not_in_the_rule_factory() -> None:
    # The deterministic trust path must not depend on a model: no LLM detector
    # *class* is returned by the rule factory.
    rule_types = {type(detector) for detector in create_all_detectors()}
    llm_types = {type(detector) for detector in create_llm_detectors(_stub())}
    assert rule_types.isdisjoint(llm_types)


def test_llm_detectors_run_through_the_shared_harness() -> None:
    assert {d.anomaly_type for d in create_llm_detectors(_stub())} == LLM_NAMES

    report = run_eval([_case()], llm_client=_stub())

    assert set(report.detectors()) >= LLM_NAMES


def test_llm_detector_fires_with_a_scripted_local_model() -> None:
    reply = '{"identical": true, "similarity": 1.0}'
    report = run_eval([_case()], llm_client=_stub(reply))

    assert report.recall("semantic_loop") == 1.0
    assert report.precision("semantic_loop") == 1.0


def test_unavailable_model_degrades_to_no_op() -> None:
    report = run_eval([_case()], llm_client=_stub(None))

    assert report.recall("semantic_loop") == 0.0
