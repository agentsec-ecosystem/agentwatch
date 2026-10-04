"""A minimal out-of-tree harness adapter (M10 #79/#203).

This module is deliberately outside `agentwatch.adapters` and uses **only** the
public plugin contract (`agentwatch.conformance.AdapterSpec`, `records`) plus
the stdlib. It proves a community harness can meet conformance without touching
private modules. `broken_spec()` is a known-bad copy used to prove the runner
actually fails a non-conforming adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch import conformance
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall

HARNESS_ID = "sample-harness"
CAPABILITIES = frozenset({"sample-tool-use"})
DOCUMENTED_GAPS = ("sample-mcp-events",)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "community"


class SampleAdapterError(ValueError):
    """Raised for an unsupported phase or a malformed event."""


def _started_at(value: Any) -> datetime:
    text = str(value)
    parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
    """Map one native sample-harness event to a record (or raise)."""
    phase = message.get("phase")
    if phase not in CAPABILITIES:
        raise SampleAdapterError(f"unsupported phase {phase!r}")
    event = message.get("event")
    if not isinstance(event, Mapping):
        raise SampleAdapterError("missing event object")
    return [
        AgentRecord(
            session_id=str(event.get("session_id") or "unknown"),
            agent=AgentIdentity(identity=str(event.get("agent") or "sample")),
            tool=ToolCall(name=str(event.get("tool_name") or "unknown")),
            outcome=Outcome.OK,
            started_at=_started_at(event.get("timestamp")),
            harness=HARNESS_ID,
            step_type=StepType.ACT,
        )
    ]


def spec() -> conformance.AdapterSpec:
    """The conforming adapter registration."""
    return conformance.AdapterSpec(
        name=HARNESS_ID,
        normalize=normalize,
        capabilities=CAPABILITIES,
        documented_gaps=DOCUMENTED_GAPS,
        error_cls=SampleAdapterError,
        fixtures_dir=FIXTURES_DIR,
    )


def _accept_anything(message: Mapping[str, Any]) -> list[AgentRecord]:
    event = message.get("event")
    safe = event if isinstance(event, Mapping) else {}
    return [
        AgentRecord(
            session_id=str(safe.get("session_id") or "unknown"),
            agent=AgentIdentity(identity="sample"),
            tool=ToolCall(name="do"),
            outcome=Outcome.OK,
            started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            harness=HARNESS_ID,
            step_type=StepType.ACT,
        )
    ]


def broken_spec() -> conformance.AdapterSpec:
    """A non-conforming copy: claims a gap it never rejects."""
    return conformance.AdapterSpec(
        name=HARNESS_ID,
        normalize=_accept_anything,
        capabilities=CAPABILITIES,
        documented_gaps=DOCUMENTED_GAPS,
        error_cls=SampleAdapterError,
        fixtures_dir=FIXTURES_DIR,
    )
