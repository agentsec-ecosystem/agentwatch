"""Versioned local pricing table (M17 S6, PRD 33).

The local store records **one token total per turn** (A5 ``session-usage``), so
this table publishes a single documented USD rate per million tokens. To avoid
under-reporting, that rate is the model's published **output-token** rate — an
upper bound on the true cost of a mixed input/output turn. Unknown models are
reported as ``tokens only, price unknown`` and are never interpolated.

The table is versioned (:data:`PRICING_VERSION`) and dated (:data:`PRICING_AS_OF`)
so a stale price is presented as a dated estimate, never as fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PRICING_VERSION = "pr1"
PRICING_AS_OF = "2026-01-01"
CURRENCY = "USD"

USAGE_TOOL = "session-usage"


@dataclass(frozen=True)
class ModelPrice:
    """A documented per-million-token rate (upper-bound, output-token basis)."""

    model: str
    usd_per_mtok: float


# Matched by longest known prefix after normalization.
PRICING: tuple[ModelPrice, ...] = (
    ModelPrice("claude-opus-4", 75.0),
    ModelPrice("claude-3-opus", 75.0),
    ModelPrice("claude-3-7-sonnet", 15.0),
    ModelPrice("claude-3-5-sonnet", 15.0),
    ModelPrice("claude-sonnet-4", 15.0),
    ModelPrice("claude-3-5-haiku", 4.0),
    ModelPrice("claude-3-haiku", 1.25),
    ModelPrice("gpt-4o-mini", 0.60),
    ModelPrice("gpt-4o", 10.0),
)

_DATE_SUFFIX = re.compile(r"-\d{6,8}$")


def normalize_model(model: str | None) -> str:
    """Lowercase, drop a provider prefix and a trailing date/build suffix."""
    if not model:
        return ""
    text = model.strip().lower()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    text = _DATE_SUFFIX.sub("", text)
    if text.endswith("-latest"):
        text = text[: -len("-latest")]
    return text


def price_for(model: str | None) -> ModelPrice | None:
    """The longest matching known price for a model id, or ``None`` if unknown."""
    candidate = normalize_model(model)
    if not candidate:
        return None
    matches = [price for price in PRICING if candidate.startswith(price.model)]
    if not matches:
        return None
    return max(matches, key=lambda price: len(price.model))


def cost_usd(tokens: int, model: str | None) -> float | None:
    """The documented dollar cost for ``tokens`` on ``model``, or ``None`` if unknown."""
    price = price_for(model)
    if price is None:
        return None
    return tokens / 1_000_000 * price.usd_per_mtok


def pricing_document() -> dict[str, object]:
    """A machine-readable view of the table (for output and docs)."""
    return {
        "version": PRICING_VERSION,
        "as_of": PRICING_AS_OF,
        "currency": CURRENCY,
        "basis": "per-million-tokens, output-token rate (upper bound)",
        "models": {price.model: price.usd_per_mtok for price in PRICING},
    }


__all__ = [
    "CURRENCY",
    "ModelPrice",
    "PRICING",
    "PRICING_AS_OF",
    "PRICING_VERSION",
    "USAGE_TOOL",
    "cost_usd",
    "normalize_model",
    "price_for",
    "pricing_document",
]
