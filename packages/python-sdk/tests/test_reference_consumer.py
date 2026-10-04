"""Reference consumer CI test (M20 S38, #261).

Runs the example in ``examples/`` against the committed fixture stream so the
reference cannot rot when the schema drifts.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = REPO_ROOT / "examples" / "security_event_consumer.py"
FIXTURE = REPO_ROOT / "examples" / "fixtures" / "events.ndjson"


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("security_event_consumer", EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_validates_the_fixture_stream() -> None:
    module = _load_example()

    valid, problems = module.validate_events(module.parse_events(FIXTURE.read_text()))

    assert problems == []
    assert [event.type.value for event in valid] == ["denied", "secret-detected"]


def test_example_cli_runs_against_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_example()

    rc = module.main(["--input", str(FIXTURE), "--json"])

    assert rc == 0
    out = capsys.readouterr()
    lines = [line for line in out.out.splitlines() if line.startswith("{")]
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] == "denied"


def test_example_rejects_a_malformed_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_example()

    valid, problems = module.validate_events([{"type": "not-a-type"}])

    assert valid == []
    assert problems and "event 0" in problems[0]

    bad = tmp_path / "bad.ndjson"
    bad.write_text('{"type": "not-a-type"}\n', encoding="utf-8")
    assert module.main(["--input", str(bad)]) == 1
    assert "rejected" in capsys.readouterr().err
