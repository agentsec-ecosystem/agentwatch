"""Install profiles (M21 S35, PRD 37).

Configuration lands on a user as a decision list at the worst moment — during
install. Four real postures cover almost every install, so we ship them as named
bundles over existing config keys (no new semantics): ``solo``, ``team``,
``compliance``, ``ci``.

A profile is printed in full (consent-first, G3) before anything is written, and
is just the CLI precedence layer under the hood — an explicit ``--set`` always
wins.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentwatch.configuration import load_config

# Each profile is a nested (TOML-shaped) bundle over existing keys.
PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "solo": {
        "privacy": {"mode": "full"},
        "store": {"retention_days": 14},
    },
    "team": {
        "privacy": {"mode": "metadata-only"},
        "store": {"retention_days": 30},
    },
    "compliance": {
        "privacy": {"mode": "metadata-only"},
        "store": {"retention_days": 365, "durability": "record", "checkpoint_every": 100},
        "redaction": {"self_test": "enabled"},
    },
    "ci": {
        "privacy": {"mode": "metadata-only"},
        "store": {"retention_days": 1, "durability": "none"},
    },
}

PROFILE_NAMES: tuple[str, ...] = tuple(PROFILE_SPECS)


class ProfileError(ValueError):
    """Raised for an unknown profile name."""


def _flatten(prefix: str, data: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            flat.update(_flatten(dotted, value))
        else:
            flat[dotted] = value
    return flat


def profile_overrides(name: str) -> dict[str, Any]:
    """The profile's settings as flattened dotted keys, or raise."""
    spec = PROFILE_SPECS.get(name)
    if spec is None:
        raise ProfileError(f"unknown profile {name!r}; expected one of {', '.join(PROFILE_NAMES)}")
    return _flatten("", spec)


def apply_profile(name: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Profile overrides with explicit ``extra`` (``--set``) winning."""
    overrides = profile_overrides(name)
    if extra:
        overrides.update(extra)
    return overrides


def validate_profiles() -> None:
    """Fail loudly if any profile bundle is invalid (drift guard, PRD 37 S35)."""
    for name in PROFILE_NAMES:
        load_config(paths=[], env={}, cli_overrides=profile_overrides(name))


def render_profile(name: str) -> str:
    """The consent-first bundle print for one profile."""
    overrides = profile_overrides(name)
    lines = [f"profile: {name}"]
    for key in sorted(overrides):
        lines.append(f"  {key} = {overrides[key]!r}")
    return "\n".join(lines)


__all__ = [
    "PROFILE_NAMES",
    "PROFILE_SPECS",
    "ProfileError",
    "apply_profile",
    "profile_overrides",
    "render_profile",
    "validate_profiles",
]
