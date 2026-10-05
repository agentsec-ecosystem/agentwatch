"""Install-integrity naming guard tests (M25 NAM-1, #312)."""

from __future__ import annotations

import pytest

from agentwatch import naming


def test_no_warning_when_our_distribution_provides_the_module() -> None:
    packages = {naming.IMPORT_NAME: [naming.DISTRIBUTION_NAME]}
    assert naming.distribution_warning(packages) is None


def test_warning_when_a_namesake_provides_the_module() -> None:
    packages = {naming.IMPORT_NAME: ["agentwatch"]}
    warning = naming.distribution_warning(packages)
    assert warning is not None
    assert naming.DISTRIBUTION_NAME in warning
    assert naming.FULL_INSTALL in warning


def test_no_warning_when_the_mapping_is_unknown() -> None:
    assert naming.distribution_warning({}) is None


def test_install_guard_emits_and_reports() -> None:
    emitted: list[str] = []

    fired = naming.install_guard(emitted.append, detector=lambda: naming.NAMESAKE_WARNING)

    assert fired is True
    assert emitted and naming.DISTRIBUTION_NAME in emitted[0]


def test_install_guard_is_silent_when_clean() -> None:
    emitted: list[str] = []
    assert naming.install_guard(emitted.append, detector=lambda: None) is False
    assert emitted == []


def test_version_banner_includes_the_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentwatch.cli.main import main

    monkeypatch.setattr(naming, "distribution_warning", lambda *a, **k: naming.NAMESAKE_WARNING)
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert naming.DISTRIBUTION_NAME in capsys.readouterr().out