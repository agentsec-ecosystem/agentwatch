"""OTel GenAI semconv pin + drift tests (M22 W4, #273)."""

from __future__ import annotations

import pytest

from agentwatch.cli.main import main
from agentwatch.semconv import (
    PINNED_ATTRIBUTES,
    SEMCONV_VERSION,
    check_drift,
    version_line,
)


def test_version_line_names_the_pin() -> None:
    assert SEMCONV_VERSION in version_line()


def test_no_drift_when_upstream_matches() -> None:
    report = check_drift(PINNED_ATTRIBUTES)
    assert report.drifted is False
    assert report.missing == ()


def test_missing_upstream_attribute_is_drift() -> None:
    upstream = [attr for attr in PINNED_ATTRIBUTES if attr != "gen_ai.tool.name"]
    report = check_drift(upstream)
    assert report.drifted is True
    assert "gen_ai.tool.name" in report.missing


def test_new_upstream_attribute_is_informational() -> None:
    report = check_drift([*PINNED_ATTRIBUTES, "gen_ai.new.thing"])
    assert report.drifted is False
    assert "gen_ai.new.thing" in report.extra


def test_version_output_carries_the_pin(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert SEMCONV_VERSION in capsys.readouterr().out
