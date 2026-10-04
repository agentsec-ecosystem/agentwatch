"""``agentwatch explain``: a narrative over already-redacted records (M7 addition M1).

The deterministic summary is **always** printed (facts: counts, tools, outcomes,
tokens, duration). A narrative is added only when an LLM is explicitly supplied;
by default none is configured, so there is no egress (C7). The LLM never touches
the redaction/validation/chain paths — it only narrates stored records (PRD 29).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from agentwatch.replay import replay_session
from agentwatch.store import RecordStore


@dataclass(frozen=True)
class ExplainResult:
    """A deterministic summary plus an optional (LLM) narrative."""

    summary: str
    narrative: str | None = None


def summarize_session(store: RecordStore, session_id: str) -> str:
    """Deterministic, factual summary of a session (no model involved)."""
    records = replay_session(store, session_id)
    if not records:
        return f"session {session_id}: no records"
    outcomes = Counter(record.outcome.value for record in records)
    tools = Counter(record.tool.name for record in records)
    tokens = sum(record.tokens or 0 for record in records)
    duration = sum(record.duration_ms or 0.0 for record in records)
    return "\n".join(
        [
            f"session {session_id}: {len(records)} records",
            "outcomes: " + ", ".join(f"{key}={value}" for key, value in sorted(outcomes.items())),
            "tools: " + ", ".join(f"{key}={value}" for key, value in tools.most_common()),
            f"tokens: {tokens}",
            f"duration_ms: {duration:.0f}",
        ]
    )


def explain_session(
    store: RecordStore,
    session_id: str,
    *,
    narrator: Callable[[str], str] | None = None,
) -> ExplainResult:
    """Deterministic summary plus an optional narrative from ``narrator``.

    ``narrator`` is only called when explicitly provided, so the default path
    performs no network or model call (local-first, no silent egress).
    """
    summary = summarize_session(store, session_id)
    narrative = narrator(summary) if narrator is not None else None
    return ExplainResult(summary=summary, narrative=narrative)
