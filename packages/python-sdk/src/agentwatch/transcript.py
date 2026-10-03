"""Transcript usage extractor (M5 A5).

Reads a Claude Code session transcript and extracts **only** token usage and the
model name — never message content. The allow-list is deliberate: the transcript
holds raw prompts/completions, so the extractor must not be able to leak them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
