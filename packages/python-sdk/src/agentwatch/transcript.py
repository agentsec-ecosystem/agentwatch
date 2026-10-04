"""Transcript usage extractor (M5 A5).

Reads a Claude Code session transcript and extracts **only** token usage and the
model name — never message content. The allow-list is deliberate: the transcript
holds raw prompts/completions, so the extractor must not be able to leak them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


@dataclass(frozen=True)
class UsageSummary:
    """Token total and model for a transcript (no content)."""

    tokens: int
    model: str | None = None


@dataclass(frozen=True)
class ToolCallSummary:
    """Tool-call count and names for a transcript (no content), M16 S2.

    This is the same A5 allow-list read as :func:`extract_usage`: it reads only
    structural metadata (``type == "tool_use"``, ``name``, ids, session, and
    timestamps) and never ``input``/``content`` values, so it cannot leak a prompt
    or an argument.
    """

    session_id: str | None
    tool_calls: int
    tools: tuple[str, ...]
    malformed: int
    first_at: str | None
    last_at: str | None


def _iter_tool_use(entry: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    content = entry.get("content")
    message = entry.get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if isinstance(item, Mapping) and item.get("type") == "tool_use":
            yield item


def extract_tool_calls(path: Path | str) -> ToolCallSummary:
    """Count ``tool_use`` calls and collect tool names, allow-listed to metadata.

    Reads counts, tool *names*, ids, session id, and timestamps only — never tool
    input or message content. Unparseable lines are counted as ``malformed`` so a
    transcript-format change is visible rather than silently lowering the count.
    """
    transcript = Path(path)
    if not transcript.exists():
        return ToolCallSummary(None, 0, (), 0, None, None)
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ToolCallSummary(None, 0, (), 0, None, None)

    session_id: str | None = None
    seen: set[str] = set()
    tools: set[str] = set()
    malformed = 0
    first_at: str | None = None
    last_at: str | None = None
    fallback = transcript.stem
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            entry: Any = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(entry, Mapping):
            malformed += 1
            continue
        if session_id is None:
            for key in ("sessionId", "session_id"):
                candidate = entry.get(key)
                if isinstance(candidate, str) and candidate:
                    session_id = candidate
                    break
        timestamp = entry.get("timestamp")
        if isinstance(timestamp, str):
            first_at = first_at or timestamp
            last_at = timestamp
        for item in _iter_tool_use(entry):
            call_id = item.get("id") or item.get("tool_use_id")
            key = (
                str(call_id)
                if isinstance(call_id, str) and call_id
                else f"{fallback}:{index}:{len(seen)}"
            )
            if key in seen:
                continue
            seen.add(key)
            name = item.get("name")
            tools.add(str(name) if isinstance(name, str) and name else "unknown")
    if session_id is None:
        session_id = fallback
    return ToolCallSummary(
        session_id=session_id,
        tool_calls=len(seen),
        tools=tuple(sorted(tools)),
        malformed=malformed,
        first_at=first_at,
        last_at=last_at,
    )


def extract_usage(path: Path | str) -> UsageSummary:
    """Sum token usage across a transcript, allow-listed to usage + model only."""
    transcript = Path(path)
    if not transcript.exists():
        return UsageSummary(tokens=0, model=None)
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return UsageSummary(tokens=0, model=None)

    tokens = 0
    model: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if isinstance(usage, dict):
            for key in _USAGE_KEYS:
                value = usage.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    tokens += int(value)
        candidate = message.get("model")
        if isinstance(candidate, str):
            model = candidate
    return UsageSummary(tokens=tokens, model=model)
