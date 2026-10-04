"""i18n/UTC baseline tests (M12 12.8).

Records are locale-independent: timestamps are always UTC ISO-8601 with an
explicit offset, regardless of the host timezone.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    SecurityEvent,
    SecurityEventType,
    ToolCall,
    _parse_iso,
)


def _localize(monkeypatch: pytest.MonkeyPatch, tz: str) -> None:
    monkeypatch.setenv("TZ", tz)
    if hasattr(time, "tzset"):
        time.tzset()


def test_record_timestamps_are_utc_iso(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        _localize(monkeypatch, "America/Los_Angeles")
        record = AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            ended_at=datetime(2026, 1, 2, 3, 4, 5, 120000, tzinfo=timezone.utc),
        )

        data = record.to_dict()

        assert data["started_at"] == "2026-01-02T03:04:05+00:00"
        assert data["ended_at"] == "2026-01-02T03:04:05.120000+00:00"
    finally:
        monkeypatch.setenv("TZ", "UTC")
        if hasattr(time, "tzset"):
            time.tzset()


def test_security_event_timestamp_is_utc() -> None:
    event = SecurityEvent(
        type=SecurityEventType.DRIFT_DETECTED,
        emitted_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        emitter="agentwatch",
    )
    assert event.to_dict()["emitted_at"] == "2026-06-01T12:00:00+00:00"


def test_parse_iso_accepts_z_and_offsets() -> None:
    assert _parse_iso("2026-01-02T03:04:05Z") == datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )
    assert _parse_iso("2026-01-02T05:04:05+02:00") == datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )
