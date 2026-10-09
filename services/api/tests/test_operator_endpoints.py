"""Attribution + SIEM-health endpoint tests (M27 UI-2 #431).

Both endpoints are read-only over optional local files; absent → empty/neutral,
malformed lines are skipped, and neither touches the DB.
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


def test_attribution_absent_store_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "record_store_path", str(tmp_path / "records.jsonl"))

    response = _client().get("/api/v1/attribution")

    assert response.status_code == 200
    assert response.json() == {"data": {"items": []}}


def test_attribution_surfaces_identity_per_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "records.jsonl"
    records = [
        {
            "session_id": "s1",
            "agent": {
                "identity": "worker",
                "principal": "hash:abc",
                "delegation_chain": ["orchestrator"],
            },
            "approval": "user",
        },
        {"session_id": "s1", "agent": {"identity": "worker"}, "approval": "user"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    monkeypatch.setattr(settings, "record_store_path", str(path))

    items = _client().get("/api/v1/attribution").json()["data"]["items"]

    assert len(items) == 1
    assert items[0]["identity"] == "worker"
    assert items[0]["approval"] == "user"
    assert items[0]["delegation_chain"] == ["orchestrator"]


def test_siem_health_absent_is_neutral(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "siem_state_path", str(tmp_path / "siem.json"))

    assert _client().get("/api/v1/siem-health").json() == {
        "data": {"targets": [], "degraded": False, "last_error": None}
    }


def test_siem_health_reads_degraded_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "siem.json"
    path.write_text(
        json.dumps({"targets": ["syslog://siem"], "degraded": True, "last_error": "down"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "siem_state_path", str(path))

    data = _client().get("/api/v1/siem-health").json()["data"]

    assert data["targets"] == ["syslog://siem"]
    assert data["degraded"] is True
    assert data["last_error"] == "down"
