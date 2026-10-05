"""W3C trace-context helpers for cross-agent trace correlation (M25 TRACE-1, #300)."""

from __future__ import annotations

from agentwatch.trace_context import (
    TraceContext,
    format_traceparent,
    parse_traceparent,
    trace_ids,
)

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN = "00f067aa0ba902b7"


def test_format_traceparent_round_trips() -> None:
    tp = format_traceparent(TRACE, SPAN, sampled=True)

    assert tp == f"00-{TRACE}-{SPAN}-01"
    ctx = parse_traceparent(tp)
    assert ctx == TraceContext(trace_id=TRACE, span_id=SPAN, sampled=True)


def test_parse_traceparent_rejects_malformed() -> None:
    for bad in ("", "garbage", "00-abc-def-01", f"00-{TRACE}-{SPAN}", f"ff-{TRACE}-{SPAN}-01"):
        assert parse_traceparent(bad) is None


def test_sampled_flag_round_trips() -> None:
    assert format_traceparent(TRACE, SPAN, sampled=False).endswith("-00")
    ctx = parse_traceparent(f"00-{TRACE}-{SPAN}-00")
    assert ctx is not None and ctx.sampled is False


def test_trace_ids_derive_from_traceparent() -> None:
    assert trace_ids(f"00-{TRACE}-{SPAN}-01") == (TRACE, SPAN)
    assert trace_ids("not-a-traceparent") is None


def test_child_span_shares_the_parent_trace_id() -> None:
    """TRACE-1 acceptance: a subagent span and its parent share one trace id."""
    parent = parse_traceparent(f"00-{TRACE}-{SPAN}-01")
    assert parent is not None

    child = format_traceparent(parent.trace_id, "00f067aa0ba902b8", sampled=parent.sampled)
    child_ctx = parse_traceparent(child)

    assert child_ctx is not None
    assert child_ctx.trace_id == parent.trace_id
    assert child_ctx.span_id != parent.span_id


def test_claude_code_adapter_carries_traceparent() -> None:
    """A hook that reports a traceparent has it propagated onto the record."""
    from agentwatch.adapters import claude_code

    message = {
        "phase": "pre",
        "event": {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_use_id": "span-x",
            "trace_id": "ignored",
            "traceparent": f"00-{TRACE}-{SPAN}-01",
        },
    }

    records = claude_code.normalize(message)

    assert records
    assert records[0].trace_id == TRACE
    assert records[0].traceparent == f"00-{TRACE}-{SPAN}-01"


def test_adapter_ignores_a_malformed_traceparent() -> None:
    from agentwatch.adapters import claude_code

    message = {
        "phase": "pre",
        "event": {"session_id": "s1", "tool_name": "Bash", "traceparent": "garbage"},
    }

    records = claude_code.normalize(message)

    assert records and records[0].traceparent is None
