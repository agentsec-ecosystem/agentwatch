"""Tests for the PRD 16 operator configuration loader.

Configuration is a security surface ([PRD 16]); these tests pin the documented
defaults, the system < user < project < env < CLI precedence, strict rejection
of unknown keys, and the fail-closed rules (F7).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agentwatch.configuration import AgentwatchConfig, ConfigError, load_config


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults_match_prd16() -> None:
    cfg = load_config(paths=[], env={})

    assert cfg.harness == "claude-code"
    assert cfg.mode == "monitor"
    assert cfg.store.path == "~/.local/share/agentwatch"
    assert cfg.store.retention_days == 30
    assert cfg.store.max_size_mb == 1024
    assert cfg.privacy.mode == "metadata-only"
    assert cfg.redaction.self_test == "enabled"
    assert cfg.export.enabled is False
    assert cfg.export.otlp_endpoint is None
    assert cfg.export.format == "otel-genai"
    assert cfg.health.endpoint == "127.0.0.1:9100"
    assert cfg.log.level == "info"


def test_config_is_frozen() -> None:
    cfg = load_config(paths=[], env={})
    with pytest.raises(FrozenInstanceError):
        cfg.store.retention_days = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Layered precedence: system < user < project < env < CLI
# ---------------------------------------------------------------------------


def test_file_precedence_later_file_wins(tmp_path: Path) -> None:
    system = _write(tmp_path / "system.toml", "log.level = 'error'\n")
    user = _write(tmp_path / "user.toml", "log.level = 'warn'\n")
    project = _write(tmp_path / "project.toml", "log.level = 'debug'\n")

    cfg = load_config(paths=[system, user, project], env={})

    assert cfg.log.level == "debug"


def test_objects_merge_recursively(tmp_path: Path) -> None:
    system = _write(
        tmp_path / "system.toml",
        "[store]\npath = '/srv/aw'\nretention_days = 7\n",
    )
    user = _write(tmp_path / "user.toml", "[store]\nmax_size_mb = 2048\n")

    cfg = load_config(paths=[system, user], env={})

    assert cfg.store.path == "/srv/aw"
    assert cfg.store.retention_days == 7
    assert cfg.store.max_size_mb == 2048


def test_env_overrides_files_and_cli_overrides_env(tmp_path: Path) -> None:
    project = _write(tmp_path / "project.toml", "[store]\nretention_days = 1\n")

    cfg = load_config(
        paths=[project],
        env={"AGENTWATCH_STORE__RETENTION_DAYS": "2"},
    )
    assert cfg.store.retention_days == 2

    cfg = load_config(
        paths=[project],
        env={"AGENTWATCH_STORE__RETENTION_DAYS": "2"},
        cli_overrides={"store.retention_days": 3},
    )
    assert cfg.store.retention_days == 3


def test_env_values_are_coerced_to_declared_types() -> None:
    cfg = load_config(
        paths=[],
        env={
            "AGENTWATCH_EXPORT__ENABLED": "true",
            "AGENTWATCH_EXPORT__OTLP_ENDPOINT": "http://collector:4317",
            "AGENTWATCH_LOG__LEVEL": "debug",
        },
    )
    assert cfg.export.enabled is True
    assert cfg.export.otlp_endpoint == "http://collector:4317"
    assert cfg.log.level == "debug"


def test_missing_config_files_are_skipped(tmp_path: Path) -> None:
    cfg = load_config(paths=[tmp_path / "does-not-exist.toml"], env={})
    assert cfg.log.level == "info"


# ---------------------------------------------------------------------------
# Strict validation / fail-closed (F7)
# ---------------------------------------------------------------------------


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    bogus = _write(tmp_path / "bogus.toml", "surprise = true\n")
    with pytest.raises(ConfigError, match="surprise"):
        load_config(paths=[bogus], env={})


def test_unknown_nested_key_is_rejected(tmp_path: Path) -> None:
    bogus = _write(tmp_path / "bogus.toml", "[store]\nnope = 1\n")
    with pytest.raises(ConfigError, match="nope"):
        load_config(paths=[bogus], env={})


def test_invalid_type_is_rejected(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.toml", "[store]\nretention_days = 'lots'\n")
    with pytest.raises(ConfigError):
        load_config(paths=[bad], env={})


def test_invalid_enum_is_rejected(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.toml", "[privacy]\nmode = 'whatever'\n")
    with pytest.raises(ConfigError):
        load_config(paths=[bad], env={})


def test_non_positive_retention_is_rejected(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.toml", "[store]\nretention_days = 0\n")
    with pytest.raises(ConfigError):
        load_config(paths=[bad], env={})


def test_export_enabled_requires_endpoint(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.toml", "[export]\nenabled = true\n")
    with pytest.raises(ConfigError, match="otlp_endpoint"):
        load_config(paths=[bad], env={})


def test_export_enabled_requires_self_test_enabled(tmp_path: Path) -> None:
    bad = _write(
        tmp_path / "bad.toml",
        "[export]\nenabled = true\notlp_endpoint = 'http://c:4317'\n"
        "[redaction]\nself_test = 'disabled'\n",
    )
    with pytest.raises(ConfigError, match="self_test"):
        load_config(paths=[bad], env={})


def test_valid_export_configuration_is_accepted(tmp_path: Path) -> None:
    good = _write(
        tmp_path / "good.toml",
        "[export]\nenabled = true\notlp_endpoint = 'http://c:4317'\n"
        "[redaction]\nself_test = 'enabled'\n",
    )
    cfg = load_config(paths=[good], env={})
    assert cfg.export.enabled is True


def test_malformed_toml_is_a_config_error(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.toml", "this is not = = toml\n")
    with pytest.raises(ConfigError):
        load_config(paths=[bad], env={})


def test_invalid_env_value_is_a_config_error() -> None:
    with pytest.raises(ConfigError):
        load_config(
            paths=[],
            env={"AGENTWATCH_STORE__RETENTION_DAYS": "not-a-number"},
        )


def test_unrelated_env_is_ignored() -> None:
    cfg = load_config(paths=[], env={"PATH": "/usr/bin", "OTHER": "x"})
    assert cfg.log.level == "info"


def test_agentwatch_config_reexported() -> None:
    assert AgentwatchConfig is not None
