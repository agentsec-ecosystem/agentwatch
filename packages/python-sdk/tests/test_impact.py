"""`agentwatch impact` + classifier tests (M17 S3, #244).

The classifier is deterministic and published, every fact carries exact/heuristic,
and the footprint groups and dedupes without scoring.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentwatch.classify import (
    CLASSIFIER_VERSION,
    CMD_DESTRUCTIVE,
    CMD_INSTALL,
    EXACT,
    FILE_DELETE,
    FILE_EDIT,
    FILE_WRITE,
    HEURISTIC,
    NETWORK,
    UNCLASSIFIED,
    VCS,
    classify_arguments,
    classify_command,
    pattern_table,
)
from agentwatch.cli.main import main
from agentwatch.impact import build_impact, render_impact
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

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


def _rec(
    session: str,
    tool: str,
    arguments: dict[str, object] | None,
    *,
    minute: int = 0,
    project: str | None = None,
    server: str | None = None,
    span: str | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=tool, arguments=arguments, server=server),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        harness="claude-code",
        project=project,
        span_id=span,
        step_type=StepType.ACT,
    )


# -- classifier --------------------------------------------------------------


def test_structured_write_is_exact() -> None:
    facts = classify_arguments({"file_path": "/repo/a.py"}, tool_name="Write")
    assert facts[0].category == FILE_WRITE
    assert facts[0].confidence == EXACT
    assert facts[0].target == "/repo/a.py"


def test_structured_edit_is_exact() -> None:
    facts = classify_arguments({"file_path": "/repo/a.py"}, tool_name="Edit")
    assert (facts[0].category, facts[0].confidence) == (FILE_EDIT, EXACT)


@pytest.mark.parametrize(
    ("command", "category", "target"),
    [
        ("rm -rf /tmp/x", CMD_DESTRUCTIVE, "rm"),
        ("pip install requests", CMD_INSTALL, "pip"),
        ("curl https://evil.example.com/a", NETWORK, "https://evil.example.com/a"),
        ("git commit -m x", VCS, "commit"),
    ],
)
def test_command_categories_are_heuristic(command: str, category: str, target: str) -> None:
    facts = classify_command(command)
    match = next(fact for fact in facts if fact.category == category)
    assert match.confidence == HEURISTIC
    assert match.target == target


def test_rm_yields_delete_and_destructive() -> None:
    facts = classify_command("rm -rf /tmp/x")
    categories = {fact.category for fact in facts}
    assert {CMD_DESTRUCTIVE, FILE_DELETE} <= categories
    delete = next(fact for fact in facts if fact.category == FILE_DELETE)
    assert delete.target == "/tmp/x"


def test_unknown_command_is_unclassified() -> None:
    facts = classify_command("echo hi")
    assert facts[0].category == UNCLASSIFIED


def test_mcp_call_is_a_network_destination() -> None:
    facts = classify_arguments({}, tool_name="mcp__srv__do", server="srv")
    assert facts[0].category == NETWORK
    assert facts[0].target == "srv"


def test_pattern_table_is_versioned_and_documented() -> None:
    table = pattern_table()
    assert table
    assert all({"id", "category", "confidence", "pattern", "detail"} <= set(row) for row in table)
    assert CLASSIFIER_VERSION == "cls1"


# -- impact ------------------------------------------------------------------


def _session_records(session: str) -> list[AgentRecord]:
    return [
        _rec(session, "Write", {"file_path": "/repo/app.py"}, minute=0, project="/repo", span="1"),
        _rec(session, "Edit", {"file_path": "/repo/app.py"}, minute=1, project="/repo", span="2"),
        _rec(session, "Bash", {"command": "rm -rf /tmp/x"}, minute=2, span="3"),
        _rec(session, "Bash", {"command": "pip install requests"}, minute=3, span="4"),
        _rec(session, "Bash", {"command": "curl https://api.example.com"}, minute=4, span="5"),
        _rec(session, "Bash", {"command": "git commit -m x"}, minute=5, span="6"),
        _rec(session, "Bash", {"command": "echo hi"}, minute=6, span="7"),
    ]


def test_impact_footprint_is_grouped_and_deduped(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for record in _session_records("s1"):
        store.append(record)

    report = build_impact(store, "s1")

    app = next(f for f in report.files if f.path == "/repo/app.py")
    assert set(app.actions) == {FILE_WRITE, FILE_EDIT}
    assert app.confidence == EXACT
    assert app.count == 2
    assert report.counts[CMD_DESTRUCTIVE] == 1
    assert report.counts[CMD_INSTALL] == 1
    assert report.counts[NETWORK] == 1
    assert report.counts[VCS] == 1
    assert report.counts[UNCLASSIFIED] >= 1
    assert report.widest_action.startswith(CMD_DESTRUCTIVE)
    assert "agentwatch impact s1" in render_impact(report)


def test_impact_reorder_is_equivalent_and_a_change_is_not(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    records = _session_records("s1")
    for record in records:
        store.append(record)
    baseline = build_impact(store, "s1")

    reordered = RecordStore(tmp_path / "r.jsonl")
    for record in reversed(records):
        reordered.append(record)
    same = build_impact(reordered, "s1")
    assert {f.path for f in same.files} == {f.path for f in baseline.files}
    assert same.counts == baseline.counts

    changed = RecordStore(tmp_path / "c.jsonl")
    for record in records:
        changed.append(record)
    changed.append(_rec("s1", "Bash", {"command": "rm -rf /var/data"}, minute=7, span="8"))
    different = build_impact(changed, "s1")
    assert different.counts[FILE_DELETE] == baseline.counts[FILE_DELETE] + 1


def test_impact_metadata_only_notes_uncaptured(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Write", None, span="1"))

    report = build_impact(store, "s1")

    assert report.arguments_captured is False
    assert report.unclassified
    assert "not captured" in report.unclassified[0].detail


def test_impact_flags_outside_project(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", "Write", {"file_path": "/elsewhere/x"}, project="/repo", span="1"))

    report = build_impact(store, "s1")

    assert report.files[0].outside_project is True


def test_cli_impact_json(isolated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = isolated / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    for record in _session_records("s1"):
        store.append(record)

    rc = main(["--set", f"store.path={store_dir}", "impact", "s1", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classifier_version"] == "cls1"
    assert payload["widest_action"].startswith("command:destructive")


def test_cli_impact_unknown_session_fails(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = isolated / "store"
    store_dir.mkdir()
    RecordStore(store_dir / "records.jsonl")
    rc = main(["--set", f"store.path={store_dir}", "impact", "nope"])
    assert rc != 0
    assert "no records" in capsys.readouterr().err
