"""Install profile tests (M21 S35, #266)."""

from __future__ import annotations

import pytest

from agentwatch.cli.main import main
from agentwatch.configuration import load_config
from agentwatch.profiles import (
    PROFILE_NAMES,
    ProfileError,
    apply_profile,
    profile_overrides,
    render_profile,
    validate_profiles,
)


def test_every_profile_validates() -> None:
    validate_profiles()
    assert set(PROFILE_NAMES) == {"solo", "team", "compliance", "ci"}


def test_unknown_profile_errors() -> None:
    with pytest.raises(ProfileError, match="unknown profile"):
        profile_overrides("nope")


def test_profile_overrides_load_through_the_loader() -> None:
    cfg = load_config(paths=[], env={}, cli_overrides=profile_overrides("compliance"))
    assert cfg.privacy.mode == "metadata-only"
    assert cfg.store.retention_days == 365
    assert cfg.store.checkpoint_every == 100


def test_set_wins_over_profile() -> None:
    merged = apply_profile("compliance", {"store.retention_days": 99})
    assert merged["store.retention_days"] == 99
    cfg = load_config(paths=[], env={}, cli_overrides=merged)
    assert cfg.store.retention_days == 99


def test_render_profile_is_full_bundle() -> None:
    text = render_profile("ci")
    assert "profile: ci" in text
    assert "privacy.mode" in text
    assert "store.retention_days" in text


def test_init_profile_dry_run_prints_before_writing(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["init", "--profile", "compliance", "--dry-run"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "profile: compliance" in out
    assert "would write" in out


def test_init_profile_with_set_resolves(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        [
            "--set",
            "store.retention_days=99",
            "init",
            "--profile",
            "compliance",
            "--dry-run",
        ]
    )

    assert rc == 0
    capsys.readouterr()
