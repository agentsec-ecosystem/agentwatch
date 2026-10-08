"""Code provenance & attribution (M30 PRV-1/PRV-2/PRV-3, PRD 53).

The record answers *what the agent did*; this module connects it to *the code it
produced*. Three parts, all **derived** views over the existing record schema and
git facts (no record-schema change):

* **PRV-3** (this section) — a content-free range+hash capture: per file-modifying
  call, the affected line range(s) and a keyed content hash, **never the content**.
  Under ``metadata-only`` the ranges+hashes still exist (they are metadata, not
  content); a harness that does not expose a range falls back to file-level
  ``heuristic`` attribution. ADR-0033.
* **PRV-1** — ``provenance <commit|range|PR|file>``: join a git fact to the
  records that produced it with a per-range confidence
  (``exact|heuristic|mixed|ambiguous|unknown``).
* **PRV-2** — Agent Trace export + git-ai notes cross-validation (``agent_trace``
  module), pinned revision + drift check.

Honesty rules (PRD 53): attribution is a claim with a confidence, never an
assumption. A commit with no recorded session says "no recorded agent activity"
— never "human". Hand edits after the agent are ``mixed``; two overlapping
sessions on one range are ``ambiguous``; gaps are flagged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentwatch.records import AgentRecord

# Bumped when the capture shape or the join semantics change (a consumer can
# branch on it). Published in docs/design/code-provenance.md.
RANGE_CAPTURE_VERSION = "prv3"
PROVENANCE_VERSION = "prv1"

EXACT = "exact"
HEURISTIC = "heuristic"
MIXED = "mixed"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"

CONFIDENCES: tuple[str, ...] = (EXACT, HEURISTIC, MIXED, AMBIGUOUS, UNKNOWN)

# A reserved key inside ``tool.arguments`` under which the content-free capture
# rides. It is *metadata* (ranges + keyed hashes), so it is legal under every
# privacy mode including ``metadata-only``; no record-schema change is needed.
AGENTWATCH_ATTRIBUTION_KEY = "agentwatch_attribution"

# Keys that would carry code content — the capture must never emit one. Used by
# the defensive ``is_content_free`` guard and the attack-pack test.
CONTENT_KEYS: frozenset[str] = frozenset(
    {
        "content",
        "new_content",
        "new_string",
        "old_string",
        "new_text",
        "text",
        "body",
        "diff",
        "patch",
        "hunk",
        "code",
    }
)

_HASH_PREFIX = "hmac-sha256:"
_FALLBACK_SALT = b"agentwatch.provenance.v1:"

_PATH_KEYS = ("file_path", "path", "notebook_path", "filename", "file")
_CONTENT_KEYS_ORDER = ("new_string", "new_content", "content", "new_text", "text", "old_string")
_START_KEYS = ("start_line", "line_start", "first_line")
_END_KEYS = ("end_line", "line_end", "last_line")
_LINE_RANGE_RE = re.compile(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$")


def _per_install_key() -> bytes | None:
    from agentwatch import flow

    return flow.hmac_key_or_none()


def _keyed_hash(text: str, *, key: bytes | None = None) -> str:
    """A stable, non-reversible handle for content.

    Keyed with the per-install HMAC key when available (the same keyed mechanism
    as identity/content-flow fingerprints) so identical content is correlatable
    within one installation but not recoverable — and never stored as content.
    """
    resolved = key if key is not None else _per_install_key()
    payload = text.encode("utf-8")
    if resolved:
        digest = hmac.new(resolved, payload, hashlib.sha256).hexdigest()
    else:
        digest = hashlib.sha256(_FALLBACK_SALT + payload).hexdigest()
    return _HASH_PREFIX + digest


@dataclass(frozen=True)
class LineRange:
    """An inclusive, 1-based line range affected by one file-modifying call."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValueError(f"invalid line range {self.start}-{self.end}")

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LineRange:
        return cls(int(data["start"]), int(data["end"]))


@dataclass(frozen=True)
class RangeCapture:
    """A content-free attribution fact for one file-modifying call (PRV-3).

    Carries the affected line range(s) and a keyed hash per captured content
    fragment; ``fallback`` is ``file-level`` when the harness exposed no range.
    Content is never a field here.
    """

    path: str | None
    ranges: tuple[LineRange, ...]
    hashes: tuple[str, ...]
    confidence: str
    fallback: str | None = None
    source_tool: str | None = None
    version: str = RANGE_CAPTURE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "path": self.path,
            "ranges": [line_range.to_dict() for line_range in self.ranges],
            "hashes": list(self.hashes),
            "confidence": self.confidence,
            "fallback": self.fallback,
            "source_tool": self.source_tool,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RangeCapture:
        ranges = data.get("ranges") or []
        hashes = data.get("hashes") or []
        return cls(
            path=data.get("path"),
            ranges=tuple(LineRange.from_dict(item) for item in ranges),
            hashes=tuple(str(item) for item in hashes),
            confidence=str(data.get("confidence", UNKNOWN)),
            fallback=data.get("fallback"),
            source_tool=data.get("source_tool"),
            version=str(data.get("version", RANGE_CAPTURE_VERSION)),
        )


def _path_from_arguments(arguments: Mapping[str, Any]) -> str | None:
    for key in _PATH_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _content_fragments(arguments: Mapping[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in _CONTENT_KEYS_ORDER:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            fragments.append(value)
    return fragments


def _int_argument(arguments: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = arguments.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _range_from_arguments(arguments: Mapping[str, Any]) -> tuple[LineRange, ...]:
    start = _int_argument(arguments, _START_KEYS)
    end = _int_argument(arguments, _END_KEYS)
    if start is not None and end is not None:
        return (LineRange(start, end),)
    raw = arguments.get("line_range")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (LineRange(int(raw[0]), int(raw[1])),)
    if isinstance(raw, str):
        match = _LINE_RANGE_RE.match(raw)
        if match is not None:
            return (LineRange(int(match.group(1)), int(match.group(2))),)
    match = _LINE_RANGE_RE.match(str(arguments.get("lines", "")))
    if match is not None:
        return (LineRange(int(match.group(1)), int(match.group(2))),)
    return ()


def capture_ranges(
    arguments: Mapping[str, Any] | None,
    *,
    tool_name: str,
    privacy_mode: str | None = None,
    key: bytes | None = None,
) -> RangeCapture:
    """Capture the content-free range+hash facts for one file-modifying call.

    Works under **every** privacy mode: the output is metadata (ranges + keyed
    hashes), never content. An explicit range makes the capture ``exact``; when
    the harness did not expose a range the capture is file-level ``heuristic``.
    """
    args: Mapping[str, Any] = arguments or {}
    path = _path_from_arguments(args)
    ranges = _range_from_arguments(args)
    hashes = tuple(_keyed_hash(fragment, key=key) for fragment in _content_fragments(args))
    if ranges:
        confidence = EXACT
        fallback = None
        if not hashes:
            hashes = (_keyed_hash(f"{tool_name}:{path}", key=key),)
    else:
        confidence = HEURISTIC
        fallback = "file-level"
        if not hashes:
            hashes = (_keyed_hash(f"{tool_name}:{path}", key=key),)
    return RangeCapture(
        path=path,
        ranges=ranges,
        hashes=hashes,
        confidence=confidence,
        fallback=fallback,
        source_tool=tool_name,
    )


def to_attribution_arguments(capture: RangeCapture) -> dict[str, Any]:
    """Wrap a capture for storage in ``tool.arguments`` (content-free)."""
    return {AGENTWATCH_ATTRIBUTION_KEY: capture.to_dict()}


def range_facts_from_record(record: AgentRecord) -> RangeCapture | None:
    """Read the reserved content-free facts off a stored record, if present."""
    arguments = record.tool.arguments
    if not isinstance(arguments, Mapping):
        return None
    raw = arguments.get(AGENTWATCH_ATTRIBUTION_KEY)
    if not isinstance(raw, Mapping):
        return None
    return RangeCapture.from_dict(raw)


def is_content_free(payload: Any) -> bool:
    """Whether a payload (recursively) carries no code-content key.

    A defensive guard: the capture shape is content-free by construction, and
    this proves it for a serialized fact before it is stored or exported.
    """
    if isinstance(payload, Mapping):
        if CONTENT_KEYS & set(payload):
            return False
        return all(is_content_free(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return all(is_content_free(item) for item in payload)
    return True


def canonical_fact(payload: Mapping[str, Any]) -> str:
    """Deterministic serialization of a fact (stable across runs)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "AGENTWATCH_ATTRIBUTION_KEY",
    "AMBIGUOUS",
    "CONFIDENCES",
    "CONTENT_KEYS",
    "EXACT",
    "HEURISTIC",
    "MIXED",
    "PROVENANCE_VERSION",
    "RANGE_CAPTURE_VERSION",
    "UNKNOWN",
    "LineRange",
    "RangeCapture",
    "canonical_fact",
    "capture_ranges",
    "is_content_free",
    "range_facts_from_record",
    "to_attribution_arguments",
]
