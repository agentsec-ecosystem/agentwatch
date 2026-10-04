"""Guard the single pathological record (M21 S36, PRD 37).

F3 caps the *store*; nothing capped a *record*. One 200 MB tool response, a
million-element argument array, or a deeply nested object can exhaust memory on
read or produce a JSONL line no consumer can process. This module applies
per-record limits with **honest, visible truncation**: an over-limit field is
shortened and the record carries a ``truncated`` marker naming the field, its
original size, and the rule. A silently shortened response is a lie about what
the agent saw; an obvious gap is not.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from agentwatch.records import AgentRecord

RULE_FIELD_SIZE = "field-size"
RULE_DEPTH = "depth"
RULE_RECORD_SIZE = "record-size"

_FIELD_MARKER = "[...]"


@dataclass(frozen=True)
class Limits:
    """Per-record capture limits (generous defaults)."""

    field_bytes: int = 65536
    record_bytes: int = 1048576
    max_depth: int = 32


@dataclass(frozen=True)
class Truncation:
    """One visible truncation: the field, its original size, and the rule."""

    field: str
    original_bytes: int
    rule: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "original_bytes": self.original_bytes, "rule": self.rule}


def _size_bytes(value: Any) -> int:
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    try:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0


def _guard_value(
    value: Any,
    *,
    path: str,
    depth: int,
    limits: Limits,
    marks: list[Truncation],
) -> Any:
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        if len(encoded) > limits.field_bytes:
            kept = encoded[: limits.field_bytes].decode("utf-8", "ignore")
            marks.append(Truncation(path, len(encoded), RULE_FIELD_SIZE))
            return kept + _FIELD_MARKER
        return value
    if isinstance(value, (dict, list)) and depth >= limits.max_depth:
        marks.append(Truncation(path, _size_bytes(value), RULE_DEPTH))
        return _FIELD_MARKER
    if isinstance(value, dict):
        return {
            key: _guard_value(
                item, path=f"{path}.{key}", depth=depth + 1, limits=limits, marks=marks
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _guard_value(item, path=f"{path}[{index}]", depth=depth + 1, limits=limits, marks=marks)
            for index, item in enumerate(value)
        ]
    return value


def guard_record(record: AgentRecord, limits: Limits | None = None) -> AgentRecord:
    """Return ``record`` with over-limit fields visibly truncated and marked.

    The record is always returned (never dropped) and always validates; a
    truncation is recorded in the ``truncated`` field.
    """
    effective = limits or Limits()
    marks: list[Truncation] = []

    arguments = record.tool.arguments
    response = record.tool.response
    if arguments is not None:
        arguments = _guard_value(
            arguments, path="tool.arguments", depth=0, limits=effective, marks=marks
        )
    if response is not None:
        response = _guard_value(
            response, path="tool.response", depth=0, limits=effective, marks=marks
        )

    tool = replace(record.tool, arguments=arguments, response=response)
    candidate = replace(record, tool=tool)
    size = _size_bytes(candidate.to_dict())

    # Total-size pass: drop the largest content field(s) until the record fits.
    if size > effective.record_bytes:
        for field_name in ("response", "arguments"):
            original = getattr(tool, field_name)
            if original is None:
                continue
            marks.append(Truncation(f"tool.{field_name}", _size_bytes(original), RULE_RECORD_SIZE))
            if field_name == "response":
                tool = replace(tool, response={"truncated": RULE_RECORD_SIZE})
            else:
                tool = replace(tool, arguments={"truncated": RULE_RECORD_SIZE})
            candidate = replace(record, tool=tool)
            if _size_bytes(candidate.to_dict()) <= effective.record_bytes:
                break

    if not marks:
        return record
    return replace(
        candidate,
        truncated={
            "fields": [mark.to_dict() for mark in marks],
            "record_bytes": effective.record_bytes,
        },
    )


__all__ = [
    "RULE_DEPTH",
    "RULE_FIELD_SIZE",
    "RULE_RECORD_SIZE",
    "Limits",
    "Truncation",
    "guard_record",
]
