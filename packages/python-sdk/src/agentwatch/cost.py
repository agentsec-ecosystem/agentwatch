"""``agentwatch cost`` — answer the captured usage (M17 S6, PRD 33).

Deterministic rollup over stored ``session-usage`` records against the versioned
:mod:`agentwatch.pricing` table. Unknown models are reported ``tokens only, price
unknown`` and never estimated; the pricing-table version and as-of date are
stamped in output. No enforcement, no budget blocking.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from agentwatch.fingerprint import _INTERNAL_TOOLS  # shared internal-tool set
from agentwatch.pricing import (
    CURRENCY,
    PRICING_AS_OF,
    PRICING_VERSION,
    USAGE_TOOL,
    cost_usd,
    normalize_model,
)
from agentwatch.query import since_cutoff
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

BY_OPTIONS = ("session", "project", "model", "tool", "day")
NO_KEY = "(none)"
UNKNOWN_MODEL = "(unknown)"


@dataclass(frozen=True)
class CostRow:
    """One rollup bucket."""

    key: str
    tokens: int
    cost_usd: float | None
    records: int
    sessions: int
    models: tuple[str, ...]


@dataclass(frozen=True)
class CostReport:
    """A cost rollup with its pricing provenance."""

    by: str
    pricing_version: str = PRICING_VERSION
    pricing_as_of: str = PRICING_AS_OF
    currency: str = CURRENCY
    since: str | None = None
    rows: tuple[CostRow, ...] = ()
    total_tokens: int = 0
    total_cost_usd: float | None = None
    unknown_models: tuple[str, ...] = ()
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "by": self.by,
            "since": self.since,
            "currency": self.currency,
            "pricing_version": self.pricing_version,
            "pricing_as_of": self.pricing_as_of,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "unknown_models": list(self.unknown_models),
            "note": self.note,
            "rows": [
                {
                    "key": row.key,
                    "tokens": row.tokens,
                    "cost_usd": row.cost_usd,
                    "records": row.records,
                    "sessions": row.sessions,
                    "models": list(row.models),
                }
                for row in self.rows
            ],
        }


def _tool_mix(records: Iterable[AgentRecord]) -> dict[str, tuple[str, ...]]:
    """Per-session distinct tool names that consumed the usage (for `--by tool`)."""
    mix: dict[str, list[str]] = {}
    for record in records:
        if record.tool.name in _INTERNAL_TOOLS:
            continue
        bucket = mix.setdefault(record.session_id, [])
        if record.tool.name not in bucket:
            bucket.append(record.tool.name)
    return {session: tuple(tools) for session, tools in mix.items()}


def _key_for(record: AgentRecord, by: str, tools: tuple[str, ...]) -> str:
    if by == "session":
        return record.session_id
    if by == "project":
        return record.project or NO_KEY
    if by == "model":
        return normalize_model(record.agent.model_version) or UNKNOWN_MODEL
    if by == "day":
        return record.started_at.date().isoformat()
    if by == "tool":
        return tools[0] if tools else NO_KEY
    raise ValueError(f"unknown --by value {by!r}; expected one of {', '.join(BY_OPTIONS)}")


@dataclass
class _Acc:
    key: str
    tokens: int = 0
    cost: float = 0.0
    known: bool = True
    records: int = 0
    sessions: set[str] | None = None
    models: set[str] | None = None

    def __post_init__(self) -> None:
        self.sessions = set()
        self.models = set()


def build_cost(
    store: RecordStore,
    *,
    by: str = "session",
    since: str | None = None,
    now: datetime | None = None,
) -> CostReport:
    """Roll up ``session-usage`` records against the versioned price table."""
    if by not in BY_OPTIONS:
        raise ValueError(f"unknown --by value {by!r}; expected one of {', '.join(BY_OPTIONS)}")
    cutoff = since_cutoff(since, now=now) if since is not None else None
    all_records = store.records()
    usage = [
        record
        for record in all_records
        if record.tool.name == USAGE_TOOL and (cutoff is None or record.started_at >= cutoff)
    ]
    if not usage:
        return CostReport(by=by, since=since, note="no session-usage records in the window")

    mix = _tool_mix(all_records)
    accumulators: dict[str, _Acc] = {}
    unknown: set[str] = set()
    for record in usage:
        tokens = int(record.tokens or 0)
        model = record.agent.model_version
        price = cost_usd(tokens, model)
        if price is None:
            unknown.add(normalize_model(model) or UNKNOWN_MODEL)
        targets = mix.get(record.session_id, ())
        if by == "tool":
            keys = list(targets) or [NO_KEY]
            share = tokens / len(keys)
            per_share_cost = (price / len(keys)) if price is not None else None
        else:
            keys = [_key_for(record, by, targets)]
            share = float(tokens)
            per_share_cost = price
        for key in keys:
            acc = accumulators.setdefault(key, _Acc(key))
            acc.tokens += int(share)
            acc.records += 1
            if acc.sessions is not None:
                acc.sessions.add(record.session_id)
            label = normalize_model(model) or UNKNOWN_MODEL
            if acc.models is not None:
                acc.models.add(label)
            if per_share_cost is None:
                acc.known = False
            else:
                acc.cost += per_share_cost

    rows = [
        CostRow(
            key=acc.key,
            tokens=acc.tokens,
            cost_usd=round(acc.cost, 6) if acc.known else None,
            records=acc.records,
            sessions=len(acc.sessions or ()),
            models=tuple(sorted(acc.models or ())),
        )
        for acc in sorted(accumulators.values(), key=lambda a: a.key)
    ]
    total_tokens = sum(row.tokens for row in rows)
    known_rows = [row for row in rows if row.cost_usd is not None]
    total_cost = round(sum(row.cost_usd or 0.0 for row in known_rows), 6) if known_rows else None
    note_parts: list[str] = []
    if unknown:
        note_parts.append("tokens only, price unknown for: " + ", ".join(sorted(unknown)))
    if any(row.cost_usd is None for row in rows):
        note_parts.append("some rows include tokens-only usage")
    return CostReport(
        by=by,
        since=since,
        rows=tuple(rows),
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        unknown_models=tuple(sorted(unknown)),
        note="; ".join(note_parts) if note_parts else None,
    )


def render_cost(report: CostReport) -> str:
    """Render a cost rollup as text, stamping the pricing version."""
    lines = [
        f"agentwatch cost --by {report.by} "
        f"(pricing {report.pricing_version} as of {report.pricing_as_of}, {report.currency})"
    ]
    if not report.rows:
        lines.append("  no session-usage records in the window")
        return "\n".join(lines)
    lines.append("KEY\tTOKENS\tCOST")
    for row in report.rows:
        cost = "tokens only" if row.cost_usd is None else f"${row.cost_usd:.4f}"
        lines.append(f"{row.key}\t{row.tokens}\t{cost}")
    total = "tokens only" if report.total_cost_usd is None else f"${report.total_cost_usd:.4f}"
    lines.append(f"TOTAL\t{report.total_tokens}\t{total}")
    if report.note:
        lines.append(f"  note: {report.note}")
    return "\n".join(lines)


__all__ = ["BY_OPTIONS", "CostReport", "CostRow", "build_cost", "render_cost"]
