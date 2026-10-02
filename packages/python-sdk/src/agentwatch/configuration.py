"""Operator configuration loader (PRD 16).

This is the configuration for the agentwatch **CLI/daemon**, not the span
instrumentation SDK. The SDK's runtime knobs live in
:mod:`agentwatch.config` (``SDKConfig``).

Configuration is a security surface, so loading is strict and **fail-closed**:
unknown keys, wrong types, invalid enumerations, or an unsafe export setup raise
:class:`ConfigError` rather than silently running with bad settings (F7).

Precedence (low -> high)::

    system  (/etc/agentwatch/config.toml)
    user    ($XDG_CONFIG_HOME/agentwatch/config.toml)
    project (./.agentwatch/config.toml)
    env     (AGENTWATCH_* — nested keys use a double underscore)
    CLI     (--set dotted.key=value)

Files are TOML. Objects merge recursively; scalar values are replaced by the
higher-precedence source. Environment keys use ``AGENTWATCH_`` followed by the
dotted key with ``__`` for nesting, e.g. ``AGENTWATCH_STORE__RETENTION_DAYS``.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib


class ConfigError(Exception):
    """Raised when configuration is malformed, unknown, or unsafe (fail-closed)."""


# ---------------------------------------------------------------------------
# Typed configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoreSection:
    path: str
    retention_days: int
    max_size_mb: int


@dataclass(frozen=True)
class PrivacySection:
    mode: str


@dataclass(frozen=True)
class RedactionSection:
    self_test: str


@dataclass(frozen=True)
class ExportSection:
    enabled: bool
    otlp_endpoint: str | None
    format: str


@dataclass(frozen=True)
class HealthSection:
    endpoint: str


@dataclass(frozen=True)
class LogSection:
    level: str


@dataclass(frozen=True)
class AgentwatchConfig:
    """Fully-resolved, validated operator configuration."""

    harness: str = "claude-code"
    mode: str = "monitor"
    store: StoreSection = field(
        default_factory=lambda: StoreSection(
            path="~/.local/share/agentwatch", retention_days=30, max_size_mb=1024
        )
    )
    privacy: PrivacySection = field(default_factory=lambda: PrivacySection(mode="metadata-only"))
    redaction: RedactionSection = field(
        default_factory=lambda: RedactionSection(self_test="enabled")
    )
    export: ExportSection = field(
        default_factory=lambda: ExportSection(
            enabled=False, otlp_endpoint=None, format="otel-genai"
        )
    )
    health: HealthSection = field(default_factory=lambda: HealthSection(endpoint="127.0.0.1:9100"))
    log: LogSection = field(default_factory=lambda: LogSection(level="info"))
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Leaf validators
# ---------------------------------------------------------------------------

Validator = Callable[[Any], Any]


def _as_str(value: Any) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"expected a string, got {type(value).__name__}")
    return value


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return _as_str(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    raise ConfigError(f"expected a boolean, got {value!r}")


def _as_positive_int(value: Any) -> int:
    # bool is an int subclass; reject it so ``retention_days = true`` fails.
    if isinstance(value, bool):
        raise ConfigError("expected a positive integer, got a boolean")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        # str.isdigit() accepts non-decimal characters ("²"), and int() then
        # raises ValueError; let int() be the single source of truth.
        try:
            result = int(value.strip())
        except ValueError:
            raise ConfigError(f"expected a positive integer, got {value!r}") from None
    else:
        raise ConfigError(f"expected a positive integer, got {value!r}")
    if result <= 0:
        raise ConfigError(f"expected a positive integer, got {result}")
    return result


def _as_enum(allowed: frozenset[str]) -> Validator:
    def validate(value: Any) -> str:
        if not isinstance(value, str) or value not in allowed:
            options = ", ".join(sorted(allowed))
            raise ConfigError(f"expected one of [{options}], got {value!r}")
        return value

    return validate


# ---------------------------------------------------------------------------
# Schema (defaults + validators)
# ---------------------------------------------------------------------------

_PRIVACY_MODES = frozenset({"metadata-only", "truncated", "hashed", "full"})
_SELF_TEST = frozenset({"enabled", "disabled"})
_LOG_LEVELS = frozenset({"debug", "info", "warn", "error"})
_EXPORT_FORMATS = frozenset({"otel-genai"})
_MODES = frozenset({"monitor"})

_DEFAULTS: dict[str, Any] = {
    "harness": "claude-code",
    "mode": "monitor",
    "store": {"path": "~/.local/share/agentwatch", "retention_days": 30, "max_size_mb": 1024},
    "privacy": {"mode": "metadata-only"},
    "redaction": {"self_test": "enabled"},
    "export": {"enabled": False, "otlp_endpoint": None, "format": "otel-genai"},
    "health": {"endpoint": "127.0.0.1:9100"},
    "log": {"level": "info"},
}

_SCHEMA: dict[str, Any] = {
    "harness": _as_str,
    "mode": _as_enum(_MODES),
    "store": {
        "path": _as_str,
        "retention_days": _as_positive_int,
        "max_size_mb": _as_positive_int,
    },
    "privacy": {"mode": _as_enum(_PRIVACY_MODES)},
    "redaction": {"self_test": _as_enum(_SELF_TEST)},
    "export": {
        "enabled": _as_bool,
        "otlp_endpoint": _as_optional_str,
        "format": _as_enum(_EXPORT_FORMATS),
    },
    "health": {"endpoint": _as_str},
    "log": {"level": _as_enum(_LOG_LEVELS)},
}


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _nested(parts: Sequence[str], value: Any) -> dict[str, Any]:
    node: dict[str, Any] = {}
    cursor = node
    for part in parts[:-1]:
        cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return node


# Environment variables that share the AGENTWATCH_ prefix but are not config
# keys (the npx launcher uses AGENTWATCH_PYTHON to pick an interpreter;
# AGENTWATCH_SOCKET selects the daemon socket per the hook contract).
_ENV_RESERVED = frozenset({"AGENTWATCH_PYTHON", "AGENTWATCH_SOCKET"})


def _env_overlay(env: Mapping[str, str]) -> dict[str, Any]:
    overlay: dict[str, Any] = {}
    for raw_key, value in env.items():
        if not raw_key.startswith("AGENTWATCH_") or raw_key in _ENV_RESERVED:
            continue
        parts = [p.lower() for p in raw_key[len("AGENTWATCH_") :].split("__") if p]
        if not parts:
            continue
        _deep_merge(overlay, _nested(parts, value))
    return overlay


def _cli_overlay(overrides: Mapping[str, Any]) -> dict[str, Any]:
    overlay: dict[str, Any] = {}
    for dotted, value in overrides.items():
        parts = [p for p in dotted.split(".") if p]
        if not parts:
            raise ConfigError(f"invalid configuration override key: {dotted!r}")
        _deep_merge(overlay, _nested(parts, value))
    return overlay


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - message varies
        raise ConfigError(f"malformed TOML in {path}: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        # Directory, permission denied, missing, or non-UTF-8 content: all are
        # configuration errors that must fail closed, never traceback.
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration in {path} must be a table")
    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_section(section: str, data: Mapping[str, Any], schema: Mapping[str, Any]) -> Any:
    if not isinstance(schema, Mapping):  # leaf handled by caller
        raise AssertionError("internal: section schema is not a mapping")

    result: dict[str, Any] = {}
    for key, value in data.items():
        if key not in schema:
            raise ConfigError(f"unknown configuration key: {section}.{key}")
        spec = schema[key]
        if isinstance(spec, Mapping):
            if not isinstance(value, Mapping):
                raise ConfigError(f"{section}.{key} must be a table")
            result[key] = _validate_section(f"{section}.{key}", value, spec)
        else:
            validator: Validator = spec
            try:
                result[key] = validator(value)
            except ConfigError as exc:
                raise ConfigError(f"invalid {section}.{key}: {exc}") from exc
    return result


def _build_config(raw: dict[str, Any]) -> AgentwatchConfig:
    validated = _validate_section("config", raw, _SCHEMA)

    store = StoreSection(**validated["store"])
    privacy = PrivacySection(**validated["privacy"])
    redaction = RedactionSection(**validated["redaction"])
    export = ExportSection(**validated["export"])
    health = HealthSection(**validated["health"])
    log = LogSection(**validated["log"])

    if export.enabled and not export.otlp_endpoint:
        raise ConfigError("export.enabled requires export.otlp_endpoint")
    if export.enabled and redaction.self_test != "enabled":
        raise ConfigError("export.enabled requires redaction.self_test = enabled")

    warnings: list[str] = []
    if privacy.mode == "full":
        warnings.append("privacy.mode=full captures raw content; ensure this is intended")
    if export.enabled:
        warnings.append(f"export.enabled sends telemetry to {export.otlp_endpoint}")

    return AgentwatchConfig(
        harness=validated["harness"],
        mode=validated["mode"],
        store=store,
        privacy=privacy,
        redaction=redaction,
        export=export,
        health=health,
        log=log,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def default_paths() -> list[Path]:
    """Return the default config file locations, lowest precedence first."""
    paths: list[Path] = []
    if os.name == "posix":
        paths.append(Path("/etc/agentwatch/config.toml"))
    xdg = os.environ.get("XDG_CONFIG_HOME")
    user_base = Path(xdg) if xdg else Path.home() / ".config"
    paths.append(user_base / "agentwatch" / "config.toml")
    paths.append(Path.cwd() / ".agentwatch" / "config.toml")
    return paths


def load_config(
    *,
    paths: Sequence[Path] | None = None,
    required_paths: Sequence[Path] | None = None,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> AgentwatchConfig:
    """Load, merge, and validate configuration, or raise :class:`ConfigError`.

    Args:
        paths: default config files in increasing precedence (system..project).
            Missing files are skipped. ``None`` uses :func:`default_paths`.
        required_paths: explicitly-requested config files (``agentwatch
            --config``). They sit above the environment and ``--set`` overrides
            them; a missing explicit path is a :class:`ConfigError`.
        env: environment mapping; ``None`` uses ``os.environ``. Only
            ``AGENTWATCH_*`` keys are read (a few reserved names are ignored).
        cli_overrides: dotted-key overrides (highest precedence).

    Returns:
        A fully-resolved :class:`AgentwatchConfig`.

    Raises:
        ConfigError: on unknown keys, invalid values, unreadable/malformed
            files, or an unsafe export configuration — the loader never returns
            a partial config (fail-closed, F7).
    """
    merged: dict[str, Any] = deepcopy(_DEFAULTS)

    for path in paths if paths is not None else default_paths():
        candidate = Path(path)
        if candidate.exists():
            _deep_merge(merged, _read_toml(candidate))

    _deep_merge(merged, _env_overlay(os.environ if env is None else env))

    for path in required_paths or ():
        candidate = Path(path)
        if not candidate.exists():
            raise ConfigError(f"config file not found: {candidate}")
        _deep_merge(merged, _read_toml(candidate))

    _deep_merge(merged, _cli_overlay(cli_overrides or {}))

    return _build_config(merged)
