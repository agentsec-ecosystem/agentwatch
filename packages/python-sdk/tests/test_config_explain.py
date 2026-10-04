"""``config explain`` tests (M21 S34, #265)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.config_explain import explain_config, render_explanations
from agentwatch.configuration import ConfigError


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_winning_layer_and_overrides(tmp_path: Path) -> None:
    system = tmp_path / "system.toml"
    user = tmp_path / "user.toml"
    project = tmp_path / "project.toml"
    _write(system, 'log.level = "warn"\n')
    _write(user, 'log.level = "error"\n')
    _write(project, 'log.level = "debug"\n')

    (explanation,) = explain_config(
        key="log.level",
        paths=[system, user, project],
        env={},
        cli_overrides={"log.level": "info"},
    )

    assert explanation.value == "info"
    assert explanation.origin == "cli"
    assert set(explanation.overridden) == {"system", "user", "project"}


def test_default_when_no_layer_sets_it(tmp_path: Path) -> None:
    (explanation,) = explain_config(key="log.level", paths=[], env={})

    assert explanation.origin == "default"
    assert explanation.is_default is True
    assert explanation.value == "info"


def test_unknown_key_errors_naming_it(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="nope.nope"):
        explain_config(key="nope.nope", paths=[], env={})


def test_diff_lists_only_non_defaults(tmp_path: Path) -> None:
    project = tmp_path / "project.toml"
    _write(project, 'log.level = "debug"\n')

    explanations = explain_config(paths=[project], env={}, diff_only=True)

    keys = {item.key for item in explanations}
    assert "log.level" in keys
    assert "store.retention_days" not in keys


def test_never_prints_a_secret_value(tmp_path: Path) -> None:
    project = tmp_path / "project.toml"
    _write(project, 'store.path = "postgres://user:pgLEAK@db:5432/app"\n')

    (explanation,) = explain_config(key="store.path", paths=[project], env={})

    assert "pgLEAK" not in str(explanation.value)
    assert "pgLEAK" not in render_explanations([explanation])


def test_cli_config_explain_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--set", "log.level=debug", "config", "explain", "log.level", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["origin"] == "cli"
    assert payload[0]["value"] == "debug"
