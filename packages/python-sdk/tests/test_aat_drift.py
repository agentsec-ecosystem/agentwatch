"""AAT draft-revision pin + drift tests (M26 AAT-5, #315)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from agentwatch.aat import (
    AAT_DRAFT,
    AAT_DRAFT_FIELDS,
    aat_version_line,
    check_aat_drift,
)
from agentwatch.cli.main import main

REPO = Path(__file__).resolve().parents[3]


def _upstream(
    *,
    revision: str = AAT_DRAFT,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "revision": revision,
        "fields": list(AAT_DRAFT_FIELDS if fields is None else fields),
    }


def _load_script() -> ModuleType:
    path = REPO / "scripts" / "aat_drift_check.py"
    spec = importlib.util.spec_from_file_location("aat_drift_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_version_line_names_the_pin() -> None:
    assert AAT_DRAFT in aat_version_line()


def test_no_drift_when_upstream_matches() -> None:
    report = check_aat_drift(_upstream())

    assert report.drifted is False
    assert report.missing == ()


def test_simulated_revision_bump_is_drift() -> None:
    report = check_aat_drift(_upstream(revision="draft-sharif-agent-audit-trail-07"))

    assert report.drifted is True
    assert report.pinned == AAT_DRAFT
    assert report.upstream == "draft-sharif-agent-audit-trail-07"


def test_missing_upstream_field_is_drift() -> None:
    fields = [field for field in AAT_DRAFT_FIELDS if field != "record_phase"]
    report = check_aat_drift(_upstream(fields=fields))

    assert report.drifted is True
    assert "record_phase" in report.missing


def test_new_upstream_field_is_informational() -> None:
    report = check_aat_drift(_upstream(fields=[*AAT_DRAFT_FIELDS, "new_field"]))

    assert report.drifted is False
    assert "new_field" in report.extra


def test_version_output_carries_the_aat_pin(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert AAT_DRAFT in capsys.readouterr().out


def test_drift_script_passes_when_pinned(tmp_path: Path) -> None:
    path = tmp_path / "upstream.json"
    path.write_text(json.dumps(_upstream()), encoding="utf-8")

    assert script.main([str(path)]) == 0


def test_drift_script_fails_on_a_simulated_bump(tmp_path: Path) -> None:
    path = tmp_path / "upstream.json"
    path.write_text(
        json.dumps(_upstream(revision="draft-sharif-agent-audit-trail-07")), encoding="utf-8"
    )

    assert script.main([str(path)]) == 1


def test_committed_upstream_snapshot_matches_the_pin() -> None:
    snapshot = json.loads(
        (REPO / "schema" / "aat" / "upstream-revision.json").read_text(encoding="utf-8")
    )

    assert check_aat_drift(snapshot).drifted is False
