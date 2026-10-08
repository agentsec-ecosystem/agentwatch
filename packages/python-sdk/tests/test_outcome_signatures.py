"""Recurring failure signatures in ``digest`` (M30 OUT-2, #478).

Deterministic grouping of failed calls / anomalies by a versioned signature
(tool, error class, cls1 class, bd1 behavior fingerprint) with counts, trend vs
the prior window, and evidence links to ``replay``/``diff``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.digest import (
    SIGNATURES_VERSION,
    TOP_SIGNATURES,
    build_digest,
    render_digest,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)


def _rec(
    session: str,
    tool: str,
    *,
    days_ago: float,
    outcome: Outcome = Outcome.OK,
    arguments: dict[str, object] | None = None,
    response: dict[str, object] | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool, arguments=arguments, response=response),
        outcome=outcome,
        started_at=NOW - timedelta(days=days_ago),
        step_type=StepType.ACT,
        project="/repo",
    )


def _session(store: RecordStore, session: str, *, days_ago: float) -> None:
    """One session whose failed Bash call is followed by a successful read."""
    store.append(
        _rec(
            session,
            "Bash",
            days_ago=days_ago,
            outcome=Outcome.ERROR,
            arguments={"command": "pytest -q"},
            response={"error": "exit status 1"},
        )
    )
    store.append(_rec(session, "Read", days_ago=days_ago - 0.001, arguments={"file_path": "/x"}))


def test_recurring_signature_groups_counts_and_evidence(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    _session(store, "s1", days_ago=2)
    _session(store, "s2", days_ago=1.5)
    _session(store, "s3", days_ago=10)  # prior window only

    report = build_digest(store, since="7d", now=NOW)

    assert report.signatures_version == SIGNATURES_VERSION
    assert report.signatures, "expected at least one recurring signature"
    top = report.signatures[0]
    assert top.tool == "Bash"
    assert top.error_class == "exit status 1"
    assert top.cls1_class  # a real cls1 category, never blank
    assert top.fingerprint.startswith("bd1:")
    # s1 and s2 share the identical behavior sequence; s3 is the prior window.
    assert top.count == 2
    assert top.previous_count == 1
    assert top.trend == "up"
    assert set(top.sessions) == {"s1", "s2"}
    assert top.first_seen == NOW - timedelta(days=2)
    assert top.last_seen == NOW - timedelta(days=1.5)
    evidence = top.evidence()
    assert "replay s1" in evidence
    assert any(link.startswith("diff ") for link in evidence)


def test_signature_fingerprint_groups_identical_behavior(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    _session(store, "s1", days_ago=2)

    report = build_digest(store, since="7d", now=NOW)

    assert len(report.signatures) == 1
    s1_expected = "bd1:"  # sanity: digest is versioned
    assert report.signatures[0].fingerprint.startswith(s1_expected)


def test_new_signature_trend_is_new(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    _session(store, "s1", days_ago=2)

    report = build_digest(store, since="7d", now=NOW)

    assert report.signatures[0].trend == "new"


def test_no_failures_has_no_signature_section(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Read", days_ago=1, arguments={"file_path": "/x"}))

    report = build_digest(store, since="7d", now=NOW)

    assert report.signatures == ()
    markdown = render_digest(report)
    assert "Recurring failure signatures" not in markdown


def test_signature_grouping_is_deterministic_and_versioned(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    _session(store, "s1", days_ago=2)
    _session(store, "s2", days_ago=1.5)

    first = build_digest(store, since="7d", now=NOW)
    second = build_digest(store, since="7d", now=NOW)

    assert first.signatures == second.signatures
    markdown = render_digest(first)
    assert "Recurring failure signatures" in markdown
    assert SIGNATURES_VERSION in markdown


def test_ranking_prefers_higher_count_then_earlier_first_seen(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    # Two sessions with a failed Bash, one session with a failed Write.
    _session(store, "s1", days_ago=2)
    _session(store, "s2", days_ago=1.5)
    store.append(
        _rec(
            "s3",
            "Write",
            days_ago=3,
            outcome=Outcome.ERROR,
            arguments={"file_path": "/tmp/x"},
            response={"error": "permission denied"},
        )
    )

    report = build_digest(store, since="7d", now=NOW)

    assert len(report.signatures) <= TOP_SIGNATURES
    assert report.signatures[0].count == 2
    counts = [pattern.count for pattern in report.signatures]
    assert counts == sorted(counts, reverse=True)
