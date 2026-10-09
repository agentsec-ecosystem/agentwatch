"""Config key tests for the SDK sampler (M25 CFG-1, #426)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentwatch.configuration import ConfigError, load_config


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_sampling_defaults() -> None:
    cfg = load_config(paths=[], env={})

    assert cfg.sampling.enabled is True
    assert cfg.sampling.ratio == 1.0


def test_sampling_ratio_is_layered(tmp_path: Path) -> None:
    config = _write(tmp_path / "config.toml", "sampling.ratio = 0.25\n")

    cfg = load_config(paths=[config], env={})

    assert cfg.sampling.ratio == 0.25


def test_sampling_can_be_disabled(tmp_path: Path) -> None:
    config = _write(tmp_path / "config.toml", "sampling.enabled = false\n")

    cfg = load_config(paths=[config], env={})

    assert cfg.sampling.enabled is False


@pytest.mark.parametrize("value", ["1.5", "-0.1", '"half"'])
def test_invalid_ratio_is_rejected(tmp_path: Path, value: str) -> None:
    config = _write(tmp_path / "config.toml", f"sampling.ratio = {value}\n")

    with pytest.raises(ConfigError):
        load_config(paths=[config], env={})


def test_ratio_zero_is_valid(tmp_path: Path) -> None:
    config = _write(tmp_path / "config.toml", "sampling.ratio = 0.0\n")

    assert load_config(paths=[config], env={}).sampling.ratio == 0.0