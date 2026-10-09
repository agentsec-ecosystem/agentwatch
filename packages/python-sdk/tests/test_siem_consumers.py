"""SIEM reference-consumer CI test (M27 SIEM-1 #346).

Runs the OCSF 1.5.0 reference consumer against a generated stream so the SIEM
flavor cannot rot when the mapping drifts. Events-only, bounded, no store.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from agentwatch.ocsf import session_ocsf
from agentwatch.records import SecurityEvent, SecurityEventType

REPO_ROOT = Path(__file__).resolve().parents[3]
OCSF_EXAMPLE = REPO_ROOT / "examples" / "ocsf_consumer.py"

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ocsf_consumer", OCSF_EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stream() -> str:
    events = [
        (0, SecurityEvent(type=SecurityEventType.DENIED, emitted_at=AT, reason="blocked")),
        (1, SecurityEvent(type=SecurityEventType.SECRET_DETECTED, emitted_at=AT, reason="masked")),
    ]
    objects = session_ocsf(events, session_id="s1")
    return "\n".join(json.dumps(obj, sort_keys=True) for obj in objects)


def test_consumer_validates_a_generated_ocsf_stream() -> None:
    module = _load_example()

    valid, problems = module.validate_objects(module.parse_objects(_stream()))

    assert problems == []
    assert len(valid) == 2
    assert all(obj["metadata"]["version"] == "1.5.0" for obj in valid)


def test_consumer_rejects_a_wrong_version() -> None:
    module = _load_example()

    valid, problems = module.validate_objects(
        [
            {
                "metadata": {"version": "1.4.0"},
                "class_uid": 1,
                "category_uid": 2,
                "activity_id": 1,
                "time": 1,
            }
        ]
    )

    assert valid == []
    assert problems and "version" in problems[0]


def test_consumer_cli_runs_against_a_stream(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_example()
    path = tmp_path / "ocsf.ndjson"
    path.write_text(_stream() + "\n", encoding="utf-8")

    assert module.main(["--input", str(path), "--json"]) == 0
    out = capsys.readouterr()
    lines = [line for line in out.out.splitlines() if line.startswith("{")]
    assert len(lines) == 2
