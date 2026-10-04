"""Harness-drift canary tests (M16 S19, #240).

The adapter observes live frames and records a debounced, metadata-only
``harness-drift`` observation naming unrecognized *fields* (never values) and
unknown phases. Names are allow-listed and capped; additive fields are framed as
additive; a repeat within a session does not duplicate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.daemon import Daemon
from agentwatch.doctor import WARN, run_checks
from agentwatch.harness_drift import (
    HARNESS_DRIFT_TOOL,
    MAX_FIELDS,
    DriftTracker,
    harness_drift_observations,
    harness_drift_record,
    sanitize_field_name,
    seed_events,
    unknown_event_fields,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

EVENT = {
    "session_id": "s1",
    "tool_name": "Bash",
    "tool_input": {"cmd": "ls"},
    "tool_use_id": "c1",
    "timestamp": "2026-01-02T03:04:05+00:00",
}


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


# -- field-name extraction ---------------------------------------------------


def test_unknown_event_fields_names_only_and_sorted() -> None:
    event = {**EVENT, "zeta": "secret-value", "alpha": "secret-value2"}

    assert unknown_event_fields(event) == ("alpha", "zeta")


def test_known_fields_are_not_drift() -> None:
    assert unknown_event_fields(EVENT) == ()


def test_field_names_are_allow_listed_and_capped() -> None:
    weird = {**EVENT, "bad name/with spaces!": 1, "x" * 200: 2}

    names = unknown_event_fields(weird)

    assert "badnamewithspaces" in names
    assert all(all(char.isalnum() or char in "_.-" for char in name) for name in names)
    assert all(len(name) <= 64 for name in names)


def test_cardinality_is_capped() -> None:
    event = {**EVENT, **{f"field{i}": i for i in range(MAX_FIELDS + 20)}}

    assert len(unknown_event_fields(event)) == MAX_FIELDS


def test_sanitize_field_name_rejects_empty_and_non_string() -> None:
    assert sanitize_field_name("!!") is None
    assert sanitize_field_name(5) is None


# -- debounce ----------------------------------------------------------------


def test_first_unknown_field_emits_once_per_session() -> None:
    tracker = DriftTracker()

    first = tracker.observe(
        harness="claude-code", session_id="s1", event={"bogus": "v"}, phase="pre", at=START
    )
    repeat = tracker.observe(
        harness="claude-code", session_id="s1", event={"bogus": "v"}, phase="pre", at=START
    )

    assert first is not None
    assert first.fields == ("bogus",)
    assert repeat is None


def test_cross_session_debounce_suppresses_repeats() -> None:
    tracker = DriftTracker(debounce_seconds=60.0)
    tracker.observe(
        harness="claude-code", session_id="s1", event={"bogus": "v"}, phase="pre", at=START
    )

    within = tracker.observe(
        harness="claude-code",
        session_id="s2",
        event={"bogus": "v"},
        phase="pre",
        at=START + timedelta(seconds=30),
    )
    after = tracker.observe(
        harness="claude-code",
        session_id="s2",
        event={"bogus": "v"},
        phase="pre",
        at=START + timedelta(seconds=120),
    )

    assert within is None
    assert after is not None


def test_unknown_phase_is_not_additive() -> None:
    tracker = DriftTracker()

    observation = tracker.observe(
        harness="claude-code", session_id="s1", event={}, phase="brand-new", at=START
    )

    assert observation is not None
    assert observation.phase == "brand-new"
    assert observation.additive is False
    assert (
        tracker.observe(
            harness="claude-code", session_id="s1", event={}, phase="brand-new", at=START
        )
        is None
    )


def test_seed_prevents_re_reporting_after_restart(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tracker = DriftTracker()
    observation = tracker.observe(
        harness="claude-code", session_id="s1", event={"bogus": "v"}, phase="pre", at=START
    )
    assert observation is not None
    store.append(harness_drift_record(observation))

    restarted = DriftTracker(seed=seed_events(store))
    again = restarted.observe(
        harness="claude-code", session_id="s2", event={"bogus": "v"}, phase="pre", at=START
    )

    assert again is None


# -- record shape ------------------------------------------------------------


def test_record_names_fields_and_never_values(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tracker = DriftTracker()
    observation = tracker.observe(
        harness="claude-code",
        session_id="s1",
        event={"bogus": "sk-LEAK-abcdefgh"},
        phase="pre",
        at=START,
    )
    assert observation is not None

    store.append(harness_drift_record(observation, harness_version="2.1.0"))

    text = store.path.read_text(encoding="utf-8")
    assert "sk-LEAK-abcdefgh" not in text
    stored = harness_drift_observations(store)[0]
    assert stored.fields == ("bogus",)
    assert stored.harness_version == "2.1.0"
    assert stored.additive is True
    assert HARNESS_DRIFT_TOOL in text


# -- daemon integration ------------------------------------------------------


def test_daemon_records_one_debounced_observation(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    daemon = Daemon(socket_path=str(tmp_path / "d.sock"), records_path=records_path)
    message = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {**EVENT, "brand_new_field": "sk-LEAK-abcdefgh"},
    }

    daemon.handle_message(message)
    daemon.handle_message(message)

    observations = harness_drift_observations(daemon.store)
    assert len(observations) == 1
    assert observations[0].fields == ("brand_new_field",)
    assert "sk-LEAK-abcdefgh" not in records_path.read_text(encoding="utf-8")
    assert daemon.health.to_dict()["drift"][0]["fields"] == ["brand_new_field"]


def test_daemon_records_unknown_phase_by_name(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    daemon = Daemon(socket_path=str(tmp_path / "d.sock"), records_path=records_path)

    daemon.handle_message({"phase": "sideways", "harness": "claude-code", "event": EVENT})

    observations = harness_drift_observations(daemon.store)
    assert len(observations) == 1
    assert observations[0].phase == "sideways"
    assert observations[0].additive is False


# -- doctor surface ----------------------------------------------------------


def test_doctor_warns_on_drift(tmp_path: Path) -> None:
    store_path = tmp_path / "records.jsonl"
    store = RecordStore(store_path)
    tracker = DriftTracker()
    observation = tracker.observe(
        harness="claude-code", session_id="s1", event={"bogus": "v"}, phase="pre", at=START
    )
    assert observation is not None
    store.append(harness_drift_record(observation))

    from agentwatch.configuration import load_config

    cfg = load_config(paths=[], env={})
    results = run_checks(
        cfg=cfg,
        store_path=store_path,
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
    )

    drift_check = next(result for result in results if result.name == "harness-drift")
    assert drift_check.status == WARN
    assert "bogus" in drift_check.detail
