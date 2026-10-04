"""Trace an exposed secret across a session (M18 S23, PRD 34).

``secret-detected`` fires and the investigation stops: the operator learns a
secret was *seen*, not where it *went*. Each detected secret carries a stable
keyed fingerprint (never the value) so repeat sightings link, and this module
records the exposure path — first sighting, each later record with the same
fingerprint, and whether any sink was a network/write/VCS action (the S3
classifier).

The output is **evidence, not a rotation instruction**: absence of a record is not
proof of absence, so the plain line is ``no evidence of egress`` unless a
qualifying sink was observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agentwatch.classify import (
    FILE_DELETE,
    FILE_EDIT,
    FILE_WRITE,
    NETWORK,
    VCS,
    classify_record,
)
from agentwatch.records import AgentRecord, SecurityEventType

EGRESS_CATEGORIES = frozenset({NETWORK, FILE_WRITE, FILE_EDIT, FILE_DELETE, VCS})


@dataclass(frozen=True)
class SecretSighting:
    """One record in which a secret fingerprint was seen."""

    index: int
    tool: str
    at: datetime
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class SecretTrace:
    """The exposure path of one distinct credential (by kind + fingerprint)."""

    kind: str
    fingerprint: str
    first_index: int
    sightings: tuple[SecretSighting, ...] = ()
    sinks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def egress(self) -> bool:
        return bool(self.sinks)

    @property
    def verdict(self) -> str:
        return "rotate: recommended" if self.egress else "no evidence of egress"


def trace_secrets(records: list[AgentRecord]) -> tuple[SecretTrace, ...]:
    """Link secret sightings by fingerprint and classify the exposure path."""
    by_fingerprint: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for index, record in enumerate(records):
        event = record.security_event
        if event is None or event.type is not SecurityEventType.SECRET_DETECTED:
            continue
        evidence = event.evidence or {}
        kinds = evidence.get("kinds")
        kind = str(kinds[0]) if isinstance(kinds, list) and kinds else "secret"
        fingerprints = evidence.get("fingerprints")
        if isinstance(fingerprints, list) and fingerprints:
            keys = [str(item) for item in fingerprints]
        else:
            # No keyed fingerprint (legacy / unkeyed): a single, unlinked sighting.
            keys = [f"{kind}#{index}"]
        categories = tuple(
            sorted(
                {
                    fact.category
                    for fact in classify_record(record)
                    if fact.category in EGRESS_CATEGORIES
                }
            )
        )
        for key in keys:
            entry = by_fingerprint.setdefault(
                key, {"kind": kind, "index": index, "sightings": [], "sinks": set()}
            )
            sightings = entry["sightings"]
            assert isinstance(sightings, list)
            first_index = entry["index"]
            assert isinstance(first_index, int)
            sightings.append(
                SecretSighting(
                    index=index, tool=record.tool.name, at=record.started_at, categories=categories
                )
            )
            if index > first_index and categories:
                sinks = entry["sinks"]
                assert isinstance(sinks, set)
                sinks.update(categories)
            if key not in order:
                order.append(key)

    traces: list[SecretTrace] = []
    for key in order:
        entry = by_fingerprint[key]
        sightings = entry["sightings"]
        sinks = entry["sinks"]
        assert isinstance(sightings, list) and isinstance(sinks, set)
        first_index = entry["index"]
        assert isinstance(first_index, int)
        traces.append(
            SecretTrace(
                kind=str(entry["kind"]),
                fingerprint=key,
                first_index=first_index,
                sightings=tuple(sightings),
                sinks=tuple(sorted(sinks)),
            )
        )
    traces.sort(key=lambda trace: trace.first_index)
    return tuple(traces)


def render_secrets(traces: tuple[SecretTrace, ...]) -> str:
    """Render secret traces by kind/fingerprint/path — never a value."""
    lines = ["agentwatch secrets"]
    if not traces:
        lines.append("  no secret-detected events recorded")
        return "\n".join(lines)
    for trace in traces:
        path = " -> ".join(f"#{sighting.index} {sighting.tool}" for sighting in trace.sightings)
        lines.append(
            f"  {trace.kind} {trace.fingerprint[:12]} sightings={len(trace.sightings)} "
            f"{trace.verdict}"
        )
        lines.append(f"    path: {path}")
        if trace.sinks:
            lines.append(f"    sinks: {', '.join(trace.sinks)}")
    return "\n".join(lines)


__all__ = [
    "EGRESS_CATEGORIES",
    "SecretSighting",
    "SecretTrace",
    "render_secrets",
    "trace_secrets",
]
