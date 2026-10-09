"""W3C Trace Context ``traceparent`` helpers (M25 TRACE-1, PRD 41).

Correlates records across agents, hosts, and processes with the W3C Trace Context
``traceparent`` header. Fail-closed: a malformed header parses to ``None`` and the
caller keeps the record's own trace id — a correlation is never invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TRACEPARENT_VERSION = "00"
_FLAG_SAMPLED = 0x01

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace>[0-9a-f]{32})-"
    r"(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)


@dataclass(frozen=True)
class TraceContext:
    """A parsed W3C ``traceparent``: trace id, span id, and the sampled flag."""

    trace_id: str
    span_id: str
    sampled: bool


def format_traceparent(trace_id: str, span_id: str, *, sampled: bool = True) -> str:
    """Render a W3C ``traceparent``; reject ids that are not 32/16 lowercase hex.

    The all-zero trace/span id is invalid and raises ``ValueError`` (never emitted).
    """
    trace = trace_id.lower()
    span = span_id.lower()
    if not _HEX32.match(trace) or trace.strip("0") == "":
        raise ValueError(f"invalid W3C trace id: {trace_id!r}")
    if not _HEX16.match(span) or span.strip("0") == "":
        raise ValueError(f"invalid W3C span id: {span_id!r}")
    flags = f"{_FLAG_SAMPLED:02x}" if sampled else "00"
    return f"{TRACEPARENT_VERSION}-{trace}-{span}-{flags}"


def parse_traceparent(value: str) -> TraceContext | None:
    """Parse a W3C ``traceparent``, or ``None`` when malformed/unsupported (fails closed)."""
    if not isinstance(value, str):
        return None
    match = _TRACEPARENT.match(value.strip().lower())
    if match is None or match["version"] == "ff":
        return None
    trace = match["trace"]
    span = match["span"]
    if trace.strip("0") == "" or span.strip("0") == "":
        return None
    sampled = bool(int(match["flags"], 16) & _FLAG_SAMPLED)
    return TraceContext(trace_id=trace, span_id=span, sampled=sampled)


def trace_ids(value: str) -> tuple[str, str] | None:
    """``(trace_id, span_id)`` from a ``traceparent``, or ``None`` when malformed."""
    context = parse_traceparent(value)
    return (context.trace_id, context.span_id) if context is not None else None


__all__ = [
    "TRACEPARENT_VERSION",
    "TraceContext",
    "format_traceparent",
    "parse_traceparent",
    "trace_ids",
]