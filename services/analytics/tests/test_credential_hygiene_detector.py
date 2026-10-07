"""Credential-hygiene detector (M28 IDN-4, #363; PRD 44 §IDN-4).

A deterministic observation, not a verdict: a run that acted under a
shared/ambient credential is flagged so the operator can review it. The detector
reads only the exported ``agentwatch.credential_class`` attribute; it never
infers a credential the trace did not state.
"""

from __future__ import annotations

from analytics.detectors import create_all_detectors
from analytics.detectors.identity import CredentialHygieneDetector
from analytics.models import RunSummary, SpanNode


def _span(attrs: dict[str, object]) -> SpanNode:
    return SpanNode(
        span_id="s1",
        trace_id="t1",
        parent_span_id="root",
        operation_name="execute_tool",
        attributes=attrs,
    )


def _summary() -> RunSummary:
    return RunSummary(run_id="r1", agent_name="agent")


def test_fires_on_ambient_shared_credential() -> None:
    detector = CredentialHygieneDetector()

    anomaly = detector.detect(
        _summary(), [_span({"agentwatch.credential_class": "ambient/shared"})]
    )

    assert anomaly is not None
    assert anomaly.anomaly_type == "credential-hygiene"
    assert anomaly.severity == "warning"
    assert anomaly.evidence["credential_class"] == "ambient/shared"
    assert anomaly.evidence["count"] == 1


def test_fires_on_the_root_span_too() -> None:
    detector = CredentialHygieneDetector()
    root = SpanNode(
        span_id="root",
        trace_id="t1",
        operation_name="invoke_agent",
        attributes={"agentwatch.credential_class": "ambient/shared"},
        child_spans=[_span({"gen_ai.tool.name": "Bash"})],
    )

    assert detector.detect(_summary(), [root]) is not None


def test_quiet_on_a_named_credential_class() -> None:
    detector = CredentialHygieneDetector()

    anomaly = detector.detect(_summary(), [_span({"agentwatch.credential_class": "api-key"})])

    assert anomaly is None


def test_quiet_when_the_credential_is_unknown() -> None:
    detector = CredentialHygieneDetector()

    assert detector.detect(_summary(), [_span({"gen_ai.tool.name": "Bash"})]) is None


def test_registered_in_the_factory() -> None:
    types = {detector.anomaly_type for detector in create_all_detectors()}

    assert "credential-hygiene" in types
