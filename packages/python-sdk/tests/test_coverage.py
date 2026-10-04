"""Coverage reconciliation tests (M16 S2, #238).

``coverage`` compares transcript tool calls (ground truth) against distinct store
tool calls and classifies every discrepancy by cause. Transcripts are read
through the A5 allow-list extractor, so only counts and tool names — never
content — are read; ``gap:unexplained`` is zero on a clean fixture.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.coverage import (
    CAUSE_DAEMON_DOWN,
    CAUSE_HARNESS_DRIFT,
    CAUSE_HOOK_NOT_INSTALLED,
    CAUSE_QUARANTINED,
    CAUSE_TRANSCRIPT_DRIFT,
    CAUSE_TRUST_GATED,
    CAUSE_UNEXPLAINED,
    SessionCoverage,
    TranscriptCoverage,
    build_coverage,
    classify_session,
    discover_transcripts,
    is_tool_call_record,
    quarantine_counts,
    store_tool_calls,
)
from agentwatch.quarantine import QuarantineLog
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore
from agentwatch.transcript import extract_tool_calls

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path / "store"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def _record(
    session: str,
    tool: str = "Bash",
    *,
    span: str | None = None,
    step: StepType = StepType.ACT,
    harness: str | None = "claude-code",
    project: str | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START,
        span_id=span,
        step_type=step,
        harness=harness,
        project=project,
    )


def _transcript_line(session: str, call_id: str, name: str = "Bash") -> str:
    return json.dumps(
        {
            "sessionId": session,
            "timestamp": START.isoformat(),
            "message": {
                "content": [
                    {"type": "tool_use", "id": call_id, "name": name, "input": {"cmd": "ls"}}
                ]
            },
        }
    )


# -- A5 extractor / canary ---------------------------------------------------


def test_extract_tool_calls_counts_names_and_session(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text(
        "\n".join(
            [
                _transcript_line("s1", "c1", "Bash"),
                _transcript_line("s1", "c2", "Read"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = extract_tool_calls(path)

    assert summary.session_id == "s1"
    assert summary.tool_calls == 2
    assert summary.tools == ("Bash", "Read")
    assert summary.malformed == 0


def test_extract_tool_calls_dedupes_ids(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text(
        _transcript_line("s1", "c1") + "\n" + _transcript_line("s1", "c1") + "\n",
        encoding="utf-8",
    )

    assert extract_tool_calls(path).tool_calls == 1


def test_extract_tool_calls_counts_malformed(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text("{not json\n" + _transcript_line("s1", "c1") + "\n", encoding="utf-8")

    summary = extract_tool_calls(path)
    assert summary.malformed == 1
    assert summary.tool_calls == 1


def test_extractor_is_a_canary_never_reads_content(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    secret = "sk-LEAK-abcdefgh"
    path.write_text(
        json.dumps(
            {
                "sessionId": "s1",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "c1",
                            "name": "Bash",
                            "input": {"cmd": f"echo {secret}"},
                        },
                        {"type": "text", "text": secret},
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = extract_tool_calls(path)

    assert secret not in repr(summary)
    assert summary.tools == ("Bash",)


def test_discover_transcripts_reports_present_and_filters_since(tmp_path: Path) -> None:
    base = tmp_path / "projects"
    base.mkdir()
    (base / "old.jsonl").write_text(_transcript_line("old", "c1") + "\n", encoding="utf-8")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "new.jsonl").write_text(
        json.dumps(
            {
                "sessionId": "new",
                "timestamp": (START + timedelta(days=2)).isoformat(),
                "message": {"content": [{"type": "tool_use", "id": "c2", "name": "Read"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    sessions, present = discover_transcripts(tmp_path, since=START + timedelta(days=1))

    assert present is True
    assert set(sessions) == {"new"}
    missing, missing_present = discover_transcripts(tmp_path / "nope")
    assert missing == {}
    assert missing_present is False


# -- store-side counting -----------------------------------------------------


def test_store_tool_calls_dedupes_spans_and_excludes_markers() -> None:
    records = [
        _record("s1", "Bash", span="c1", step=StepType.ACT),
        _record("s1", "Bash", span="c1", step=StepType.OBSERVE),
        _record("s1", "Read", span="c2", step=StepType.OBSERVE),
        _record("s1", "recording-gap", step=StepType.ACT),
        _record("s1", "session-start", harness=None, step=StepType.ACT),
        _record("s1", "recorder-installed", harness=None, step=StepType.ACT),
    ]
    assert is_tool_call_record(records[0]) is True
    assert is_tool_call_record(records[3]) is False
    assert is_tool_call_record(records[4]) is False

    counts, _projects = store_tool_calls(records)
    assert counts == {"s1": 2}


# -- classification ----------------------------------------------------------


def _transcript(calls: int, *, malformed: int = 0) -> TranscriptCoverage:
    return TranscriptCoverage(
        session_id="s1", tool_calls=calls, tools=("Bash",), malformed=malformed
    )


def test_clean_session_has_no_gaps() -> None:
    coverage = classify_session(
        "s1",
        project=None,
        transcript=_transcript(3),
        store_calls=3,
        hooks_installed=True,
        gap_count=0,
        hook_error_count=0,
        drift_count=0,
        quarantine_count=0,
    )

    assert coverage.gaps == ()
    assert coverage.capture_rate == 1.0
    assert coverage.unknown is False


def test_unknown_when_no_transcript() -> None:
    coverage = classify_session(
        "s1",
        project=None,
        transcript=None,
        store_calls=3,
        hooks_installed=True,
        gap_count=0,
        hook_error_count=0,
        drift_count=0,
        quarantine_count=0,
    )

    assert coverage.unknown is True
    assert coverage.capture_rate is None


def _classify(
    *,
    transcript: TranscriptCoverage | None,
    store_calls: int,
    hooks_installed: bool = True,
    gap_count: int = 0,
    hook_error_count: int = 0,
    drift_count: int = 0,
    quarantine_count: int = 0,
) -> SessionCoverage:
    return classify_session(
        "s1",
        project=None,
        transcript=transcript,
        store_calls=store_calls,
        hooks_installed=hooks_installed,
        gap_count=gap_count,
        hook_error_count=hook_error_count,
        drift_count=drift_count,
        quarantine_count=quarantine_count,
    )


def _causes(coverage: SessionCoverage) -> list[str]:
    return [gap.cause for gap in coverage.gaps]


def test_daemon_down_cause() -> None:
    coverage = _classify(transcript=_transcript(3), store_calls=1, gap_count=1)
    assert _causes(coverage) == [CAUSE_DAEMON_DOWN]


def test_hook_error_maps_to_daemon_down() -> None:
    coverage = _classify(transcript=_transcript(3), store_calls=1, hook_error_count=1)
    assert _causes(coverage) == [CAUSE_DAEMON_DOWN]


def test_quarantined_cause() -> None:
    coverage = _classify(transcript=_transcript(3), store_calls=1, quarantine_count=1)
    assert _causes(coverage) == [CAUSE_QUARANTINED]


def test_hook_not_installed_cause() -> None:
    coverage = _classify(transcript=_transcript(3), store_calls=1, hooks_installed=False)
    assert _causes(coverage) == [CAUSE_HOOK_NOT_INSTALLED]


def test_transcript_format_drift_cause() -> None:
    coverage = _classify(transcript=_transcript(3, malformed=1), store_calls=1)
    assert _causes(coverage) == [CAUSE_TRANSCRIPT_DRIFT]


def test_harness_drift_cause() -> None:
    coverage = _classify(transcript=_transcript(3), store_calls=1, drift_count=1)
    assert _causes(coverage) == [CAUSE_HARNESS_DRIFT]


def test_trust_gated_when_hooks_installed_but_store_empty() -> None:
    coverage = classify_session(
        "s1",
        project=None,
        transcript=_transcript(3),
        store_calls=0,
        hooks_installed=True,
        gap_count=0,
        hook_error_count=0,
        drift_count=0,
        quarantine_count=0,
    )

    assert [gap.cause for gap in coverage.gaps] == [CAUSE_TRUST_GATED]


def test_unexplained_when_partial_with_no_evidence() -> None:
    coverage = classify_session(
        "s1",
        project=None,
        transcript=_transcript(3),
        store_calls=1,
        hooks_installed=True,
        gap_count=0,
        hook_error_count=0,
        drift_count=0,
        quarantine_count=0,
    )

    assert [gap.cause for gap in coverage.gaps] == [CAUSE_UNEXPLAINED]
    assert coverage.unexplained == 2


# -- quarantine attribution --------------------------------------------------


def test_quarantine_counts_read_session_metadata(tmp_path: Path) -> None:
    log = QuarantineLog(tmp_path / "quarantine.jsonl")
    log.add(json.dumps({"session_id": "s1", "tool_name": "Bash"}), reason="normalize-error")
    log.add("not json", reason="malformed-line")

    counts = quarantine_counts(log)

    assert counts["s1"] == 1
    assert counts[None] == 1


# -- build_coverage ----------------------------------------------------------


def test_build_coverage_totals_and_unknown(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash", span="c1", step=StepType.OBSERVE))
    transcripts = {"s1": _transcript(2), "s2": TranscriptCoverage(session_id="s2", tool_calls=1)}

    report = build_coverage(
        store, transcripts=transcripts, transcripts_present=True, hooks_installed=True
    )

    assert report.totals["transcript_calls"] == 3
    assert report.totals["store_calls"] == 1
    assert report.totals["gaps"][CAUSE_UNEXPLAINED] == 1
    # s2 has no store session but has a transcript -> fully missing, classified.
    s2 = next(s for s in report.sessions if s.session_id == "s2")
    assert s2.transcript_calls == 1
    assert s2.store_calls == 0


def test_build_coverage_marks_unknown_without_transcripts(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash", span="c1", step=StepType.OBSERVE))

    report = build_coverage(store, transcripts={}, transcripts_present=False, hooks_installed=True)

    assert report.transcripts_present is False
    assert report.sessions[0].unknown is True


# -- CLI ---------------------------------------------------------------------


def test_cli_coverage_reports_capture_and_gap(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = isolated / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    store.append(_record("s1", "Bash", span="c1", step=StepType.OBSERVE, project="/proj"))
    transcripts = isolated / "projects" / "p"
    transcripts.mkdir(parents=True)
    (transcripts / "s1.jsonl").write_text(
        _transcript_line("s1", "c1") + "\n" + _transcript_line("s1", "c2") + "\n",
        encoding="utf-8",
    )

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "coverage",
            "--transcripts",
            str(isolated / "projects"),
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "s1: 1/2 calls" in out
    assert "gap:" in out


def test_cli_coverage_json(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = isolated / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl")

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "coverage",
            "--transcripts",
            str(isolated / "missing"),
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["transcripts_present"] is False


# -- merge / filters / render ------------------------------------------------


def test_discover_transcripts_merges_a_session_across_files(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "s1.jsonl").write_text(_transcript_line("s1", "c1") + "\n", encoding="utf-8")
    (b / "s1.jsonl").write_text(_transcript_line("s1", "c2", "Read") + "\n", encoding="utf-8")

    sessions, present = discover_transcripts(tmp_path)

    assert present is True
    assert sessions["s1"].tool_calls == 2
    assert sessions["s1"].tools == ("Bash", "Read")


def test_store_tool_calls_counts_anonymous_and_project() -> None:
    records = [
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=START,
            harness="claude-code",
            step_type=StepType.ACT,
            project="/proj",
        ),
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Read"),
            outcome=Outcome.OK,
            started_at=START,
            harness="claude-code",
            step_type=StepType.OBSERVE,
        ),
    ]

    counts, projects = store_tool_calls(records)

    assert counts == {"s1": 2}
    assert projects == {"s1": "/proj"}


def test_build_coverage_session_and_project_filters(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record("s1", "Bash", span="c1", project="/p1"))
    store.append(_record("s2", "Read", span="c2", project="/p2"))
    transcripts = {
        "s1": TranscriptCoverage(session_id="s1", tool_calls=1),
        "s2": TranscriptCoverage(session_id="s2", tool_calls=1),
    }

    by_session = build_coverage(
        store, transcripts=transcripts, transcripts_present=True, session="s2"
    )
    assert [s.session_id for s in by_session.sessions] == ["s2"]

    by_project = build_coverage(
        store, transcripts=transcripts, transcripts_present=True, project="/p1"
    )
    assert [s.session_id for s in by_project.sessions] == ["s1"]


def test_report_render_without_transcripts(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    report = build_coverage(store, transcripts={}, transcripts_present=False)

    text = report.render()

    assert "transcripts: not present" in text
    assert "unexplained 0" in text
