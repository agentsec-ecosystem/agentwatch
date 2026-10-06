"""Detector-telemetry endpoint tests (M27 UI-2 #431).

The endpoint is read-only over a local, content-free NDJSON file (DET-5); an
absent file is empty, malformed lines are skipped, and it never touches the DB.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_absent_file_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detector_telemetry_path", str(tmp_path / "nope.ndjson"))

    response = _client().get("/api/v1/detector-telemetry")

    assert response.status_code == 200
    assert response.json() == {"data": {"items": []}}


def test_reads_content_free_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "telemetry.ndjson"
    markers = [
        {"kind": "detector-telemetry", "detector": "loop", "outcome": "fired"},
        {"kind": "detector-telemetry", "detector": "retry", "outcome": "suppressed"},
    ]
    path.write_text("\n".join(json.dumps(m) for m in markers) + "\n", encoding="utf-8")
    monkeypatch.setattr(settings, "detector_telemetry_path", str(path))

    items = _client().get("/api/v1/detector-telemetry").json()["data"]["items"]

    assert [item["detector"] for item in items] == ["loop", "retry"]


def test_malformed_lines_are_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "telemetry.ndjson"
    path.write_text('{not-json}\n{"detector": "loop", "outcome": "fired"}\n', encoding="utf-8")
    monkeypatch.setattr(settings, "detector_telemetry_path", str(path))

    items = _client().get("/api/v1/detector-telemetry").json()["data"]["items"]

    assert [item["detector"] for item in items] == ["loop"]
