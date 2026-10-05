"""Security-relevant-always-on sampler tests (M25 SDK-2, #307).

Contract (design/sdk-lifecycle.md): security events, denials, secret detections,
errors, and approval decisions are never sampled out; ordinary successful steps are
ratio-sampled deterministically (stable across replays); the outcome is transparent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Approval,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    ToolCall,
)
from agentwatch.sampling import SampleDecision, SecurityRelevantSampler

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(**overrides: object) -> AgentRecord:
    base: dict[str, object] = {
        "session_id": "sess-1",
        "agent": AgentIdentity(identity="a"),
        "tool": ToolCall(name="Bash"),
        "outcome": Outcome.OK,
        "started_at": AT,
        "span_id": "span-1",
    }
    base.update(overrides)
    return AgentRecord(**base)  # type: ignore[arg-type]


def test_security_events_are_never_sampled_out() -> None:
    record = _record(
        outcome=Outcome.DENIED,
        security_event=SecurityEvent(
            type=SecurityEventType.DENIED, emitted_at=AT, emitter="agentpolicy"
        ),
    )
    assert SecurityRelevantSampler().should_sample(record, ratio=0.0) is SampleDecision.ALWAYS


def test_denials_and_errors_are_never_sampled_out() -> None:
    sampler = SecurityRelevantSampler()
    denied = sampler.should_sample(_record(outcome=Outcome.DENIED), ratio=0.0)
    errored = sampler.should_sample(_record(outcome=Outcome.ERROR), ratio=0.0)
    assert denied is SampleDecision.ALWAYS
    assert errored is SampleDecision.ALWAYS


def test_approval_decisions_are_never_sampled_out() -> None:
    record = _record(approval=Approval.USER)
    assert SecurityRelevantSampler().should_sample(record, ratio=0.0) is SampleDecision.ALWAYS


def test_ratio_one_keeps_ordinary_steps() -> None:
    assert (
        SecurityRelevantSampler().should_sample(_record(), ratio=1.0) is SampleDecision.SAMPLED
    )


def test_ratio_zero_drops_ordinary_steps() -> None:
    assert (
        SecurityRelevantSampler().should_sample(_record(), ratio=0.0)
        is SampleDecision.SAMPLED_OUT
    )


def test_sampling_is_deterministic_across_replays() -> None:
    sampler = SecurityRelevantSampler()
    record = _record()
    first = sampler.should_sample(record, ratio=0.5)
    for _ in range(20):
        assert sampler.should_sample(record, ratio=0.5) is first


def test_sampling_ratio_is_honoured_roughly() -> None:
    sampler = SecurityRelevantSampler()
    kept = sum(
        sampler.should_sample(_record(span_id=f"span-{i}"), ratio=0.5) is SampleDecision.SAMPLED
        for i in range(400)
    )
    assert 140 <= kept <= 260  # ~50% of 400, generous bounds for a stable hash


def test_decision_has_a_stable_wire_value() -> None:
    assert SampleDecision.ALWAYS.value == "always"
    assert SampleDecision.SAMPLED.value == "sampled"
    assert SampleDecision.SAMPLED_OUT.value == "sampled-out"