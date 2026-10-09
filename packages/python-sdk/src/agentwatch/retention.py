"""Retention profiles (M28 CMP-3, PRD 44 §CMP-3).

A retention *window* is a policy choice, not a hand-edited number. Profiles give
it a name a compliance report can cite:

- ``high-risk-12mo`` — AAT §9 high-risk systems (12 months).
- ``general-6mo`` — general operational traces (6 months).
- ``custom`` — the operator-configured ``store.retention_days``.

Profiles only choose the window; :meth:`RecordStore.apply_retention` still
tombstones (never hard-deletes) and the change is recorded as a
``retention-changed`` marker (S5).
"""

from __future__ import annotations

from dataclasses import dataclass

CUSTOM_PROFILE = "custom"


@dataclass(frozen=True)
class RetentionProfile:
    """A named retention window."""

    name: str
    retention_days: int
    description: str


RETENTION_PROFILES: dict[str, RetentionProfile] = {
    "high-risk-12mo": RetentionProfile(
        "high-risk-12mo", 365, "AAT §9 high-risk window (12 months)"
    ),
    "general-6mo": RetentionProfile("general-6mo", 180, "general operational window (6 months)"),
}


def profile_names() -> tuple[str, ...]:
    """Every selectable profile name, custom last (the fallback)."""
    return (*RETENTION_PROFILES, CUSTOM_PROFILE)


def resolve_retention_profile(name: str | None, *, retention_days: int) -> RetentionProfile:
    """Resolve a profile name to a window; ``None``/``custom`` use the config.

    An unknown name fails loudly rather than silently falling back to a default
    window the operator did not choose.
    """
    if name is None or name == CUSTOM_PROFILE:
        return RetentionProfile(CUSTOM_PROFILE, retention_days, "operator-configured window")
    try:
        return RETENTION_PROFILES[name]
    except KeyError:
        options = ", ".join(profile_names())
        raise ValueError(f"unknown retention profile {name!r}; choose from {options}") from None


__all__ = [
    "CUSTOM_PROFILE",
    "RETENTION_PROFILES",
    "RetentionProfile",
    "profile_names",
    "resolve_retention_profile",
]
