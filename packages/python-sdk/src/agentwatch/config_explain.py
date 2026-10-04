"""``agentwatch config explain`` — why is this value what it is? (M21 S34, PRD 37).

PRD 16 merges five precedence layers (system < user < project < env < CLI) with
strict unknown-key rejection. This module answers the question that design
invites: which layer won, and what did it override. Read-only; it never writes
and never prints a secret-bearing value.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.configuration import (
    _DEFAULTS,
    ConfigError,
    _cli_overlay,
    _env_overlay,
    _read_toml,
    default_paths,
)
from agentwatch.secrets import redact_secrets

LAYERS = ("system", "user", "project", "env", "cli")
DEFAULT_LAYER = "default"


@dataclass(frozen=True)
class ConfigLayer:
    """One precedence layer's dotted-key values and where it came from."""

    name: str
    source: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KeyExplanation:
    """The effective value of one key, its origin, and the layers it overrode."""

    key: str
    value: Any
    origin: str
    source: str
    overridden: tuple[str, ...] = ()
    default: Any = None

    @property
    def is_default(self) -> bool:
        return self.origin == DEFAULT_LAYER

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "origin": self.origin,
            "source": self.source,
            "overridden": list(self.overridden),
            "is_default": self.is_default,
        }


def _flatten(prefix: str, data: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            flat.update(_flatten(dotted, value))
        else:
            flat[dotted] = value
    return flat


def config_layers(
    *,
    paths: Sequence[Path] | None = None,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> list[ConfigLayer]:
    """The five precedence layers as flattened, ordered dotted-key dicts."""
    resolved = list(paths) if paths is not None else default_paths()
    layers: list[ConfigLayer] = []
    for index, path in enumerate(resolved):
        candidate = Path(path)
        name = LAYERS[index] if index < 3 else f"file{index}"
        values = _flatten("", _read_toml(candidate)) if candidate.exists() else {}
        layers.append(ConfigLayer(name=name, source=str(candidate), values=values))
    layers.append(
        ConfigLayer(
            name="env",
            source="environment (AGENTWATCH_*)",
            values=_flatten("", _env_overlay(os.environ if env is None else env)),
        )
    )
    layers.append(
        ConfigLayer(
            name="cli",
            source="--set",
            values=_flatten("", _cli_overlay(cli_overrides or {})),
        )
    )
    return layers


def _known_keys() -> set[str]:
    return set(_flatten("", _DEFAULTS))


def _mask(value: Any) -> Any:
    """Never print a secret-bearing value (belt-and-braces; PRD 18 says none exist)."""
    if isinstance(value, str):
        masked, kinds = redact_secrets(value)
        if kinds:
            return masked
        return value
    return value


def explain_config(
    *,
    key: str | None = None,
    paths: Sequence[Path] | None = None,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
    diff_only: bool = False,
) -> list[KeyExplanation]:
    """Explain one key (or every key), with origin and overridden layers.

    Raises:
        ConfigError: for an unknown key, naming it (never a silent default).
    """
    defaults = _flatten("", _DEFAULTS)
    layers = config_layers(paths=paths, env=env, cli_overrides=cli_overrides)

    effective: dict[str, Any] = dict(defaults)
    for layer in layers:
        effective.update(layer.values)

    if key is not None and key not in effective:
        known = ", ".join(sorted(_known_keys()))
        raise ConfigError(f"unknown configuration key: {key!r}; known keys: {known}")

    keys = [key] if key is not None else sorted(effective)
    explanations: list[KeyExplanation] = []
    for dotted in keys:
        contributors = [layer for layer in layers if dotted in layer.values]
        if contributors:
            origin = contributors[-1].name
            source = contributors[-1].source
            overridden = tuple(layer.name for layer in contributors[:-1])
        else:
            origin = DEFAULT_LAYER
            source = DEFAULT_LAYER
            overridden = ()
        default_value = defaults.get(dotted)
        is_default = origin == DEFAULT_LAYER or effective.get(dotted) == default_value
        if diff_only and is_default:
            continue
        explanations.append(
            KeyExplanation(
                key=dotted,
                value=_mask(effective.get(dotted)),
                origin=origin,
                source=source,
                overridden=overridden,
                default=_mask(default_value),
            )
        )
    return explanations


def render_explanations(explanations: Sequence[KeyExplanation]) -> str:
    lines = ["agentwatch config explain"]
    if not explanations:
        lines.append("  (no keys differ from defaults)")
        return "\n".join(lines)
    for item in explanations:
        lines.append(f"  {item.key} = {item.value!r}  [{item.origin}]")
        if item.overridden:
            lines.append(f"    overrides: {', '.join(item.overridden)}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_LAYER",
    "LAYERS",
    "ConfigLayer",
    "KeyExplanation",
    "config_layers",
    "explain_config",
    "render_explanations",
]
