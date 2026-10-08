"""``capability-loaded`` attribution (M30 CAP-3, #460; PRD 52).

Where a harness exposes loads, agentwatch records a metadata-only
``capability-loaded`` step (name, kind, scope, digest) so ``replay``/``impact``/
``search`` can show it as *context* — wording is "followed the load of", never
"caused by". The per-harness load-exposure matrix is published and CI-checked.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.capabilities import (
    CAP_KIND_SKILL,
    CAPABILITY_LOADED_TOOL,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    LOAD_EXPOSURE,
    SCOPE_USER,
    capability_loaded_record,
    capability_loads,
    load_exposure_matrix,
    record_capability_load,
)
from agentwatch.cli.main import main
from agentwatch.impact import build_impact, render_impact
from agentwatch.query import search
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
DESIGN_DOC = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "design"
    / "capability-supply-chain.md"
)


def _tool(session: str, name: str, *, minute: int, arguments=None) -> AgentRecord:  # type: ignore[no-untyped-def]
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name, arguments=arguments),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        step_type=StepType.ACT,
    )


def test_load_record_is_metadata_only() -> None:
    record = capability_loaded_record(
        "s1", "pdf", kind=CAP_KIND_SKILL, scope=SCOPE_USER, digest="a" * 64, at=START
    )
    assert record.tool.name == CAPABILITY_LOADED_TOOL
    arguments = record.tool.arguments or {}
    assert arguments["name"] == "pdf"
    assert arguments["kind"] == CAP_KIND_SKILL
    assert arguments["digest"] == "a" * 64
    assert "content" not in arguments
    assert record.tool.privacy_mode.value == "metadata-only"


def test_capability_loads_lists_loads(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "Read", minute=0))
    record_capability_load(store, "s1", "pdf", digest="a" * 64, at=START + timedelta(minutes=1))

    loads = capability_loads(store.records())

    assert [load.name for load in loads] == ["pdf"]
    assert loads[0].kind == CAP_KIND_SKILL
    assert loads[0].context_line() == "followed the load of skill pdf (user)"


def test_impact_lists_capabilities_loaded_in_the_session(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    record_capability_load(store, "s1", "pdf", digest="a" * 64, at=START)
    store.append(_tool("s1", "Write", minute=1, arguments={"file_path": "/repo/a.py"}))

    report = build_impact(store, "s1")
    assert [load.name for load in report.capabilities] == ["pdf"]

    rendered = render_impact(report)
    assert "followed the load of skill pdf" in rendered
    assert "caused" not in rendered.lower()


def test_search_capability_returns_calls_after_a_load(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "Read", minute=0))
    record_capability_load(store, "s1", "pdf", at=START + timedelta(minutes=5))
    store.append(_tool("s1", "Write", minute=10, arguments={"file_path": "/repo/b.py"}))
    store.append(_tool("s2", "Read", minute=20))

    results = search(store, capability="pdf")

    names = [(record.session_id, record.tool.name) for record in results]
    assert ("s1", CAPABILITY_LOADED_TOOL) in names
    assert ("s1", "Write") in names
    assert ("s1", "Read") not in names  # before the load
    assert all(session != "s2" for session, _ in names)  # other sessions unaffected


def test_replay_shows_loads_inline(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    record_capability_load(store, "s1", "pdf", at=START)
    store.append(_tool("s1", "Read", minute=1))

    rc = main(["--set", f"store.path={store_dir}", "replay", "s1"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "followed the load of skill pdf" in out


def test_cli_search_capability(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    record_capability_load(store, "s1", "pdf", at=START)
    store.append(_tool("s1", "Write", minute=2, arguments={"file_path": "/repo/b.py"}))

    rc = main(["--set", f"store.path={store_dir}", "search", "--capability", "pdf", "--json"])

    assert rc == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(line["tool"]["name"] == CAPABILITY_LOADED_TOOL for line in lines)
    assert any(line["tool"]["name"] == "Write" for line in lines)


def test_exposure_matrix_is_published_and_honest() -> None:
    matrix = load_exposure_matrix()
    assert {row.harness for row in matrix} == {"claude-code", "cursor", "codex-cli", "gemini-cli"}
    assert next(row for row in matrix if row.harness == "claude-code").status == COVERAGE_PARTIAL
    assert next(row for row in matrix if row.harness == "cursor").status == COVERAGE_NONE

    doc = DESIGN_DOC.read_text(encoding="utf-8")
    assert "Load exposure" in doc
    for row in LOAD_EXPOSURE:
        assert row.harness in doc
        assert row.status in doc
