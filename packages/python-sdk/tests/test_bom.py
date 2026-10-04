"""Agent Bill of Materials tests (M15 S9, #233).

A BOM is an *observed* CycloneDX document with a mandatory coverage block; an
unknown model is listed by name without a fabricated version.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.bom import (
    build_bom,
    to_agentwatch_json,
    to_cyclonedx,
    validate_cyclonedx,
)
from agentwatch.cli.main import main
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.store_access import store_accesses

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(
    *,
    session: str = "s1",
    agent: AgentIdentity | None = None,
    tool: ToolCall | None = None,
    harness: str | None = "claude-code",
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=agent or AgentIdentity(identity="a", name="triage", model_version="claude-x"),
        tool=tool or ToolCall(name="issue_get", server="github"),
        outcome=Outcome.OK,
        started_at=START,
        harness=harness,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(
            agent=AgentIdentity(
                identity="a",
                name="triage",
                model_version="claude-x-1",
                prompt_version="sha256:abc",
            )
        )
    )
    return store


def test_bom_components(tmp_path: Path) -> None:
    bom = build_bom(_store(tmp_path))

    by_type: dict[str, list[str]] = {}
    for component in bom.components:
        by_type.setdefault(component.type, []).append(component.name)

    assert by_type["machine-learning-model"] == ["triage"]
    assert by_type["service"] == ["github"]
    assert by_type["data"] == ["prompt/ruleset"]
    assert by_type["application"] == ["claude-code"]
    assert by_type["library"] == ["agentwatch"]


def test_tool_surface_digest_is_stable(tmp_path: Path) -> None:
    bom = build_bom(_store(tmp_path))
    server = next(c for c in bom.components if c.name == "github")
    props = dict(server.properties)
    first = props["agentwatch:tool-surface-digest"]
    rebuilt = build_bom(_store(tmp_path))
    second = dict(next(c for c in rebuilt.components if c.name == "github").properties)[
        "agentwatch:tool-surface-digest"
    ]
    assert first == second
    assert props["agentwatch:observed-tools"] == "issue_get"


def test_coverage_is_mandatory_and_honest(tmp_path: Path) -> None:
    bom = build_bom(_store(tmp_path))
    coverage = bom.coverage.to_dict()

    assert coverage["basis"] == "observed"
    assert coverage["records"] == 1
    assert coverage["sessions"] == ["s1"]
    assert coverage["window"]["start"] == START.isoformat()
    assert "installed on this machine" in coverage["does_not_claim"]


def test_cyclonedx_document_validates(tmp_path: Path) -> None:
    document = to_cyclonedx(build_bom(_store(tmp_path)))

    assert validate_cyclonedx(document) == []
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    coverage_prop = next(
        p for p in document["metadata"]["properties"] if p["name"] == "agentwatch:coverage"
    )
    assert json.loads(coverage_prop["value"])["basis"] == "observed"


def test_unknown_model_has_no_fabricated_version(tmp_path: Path) -> None:
    # An observed record without a model_version contributes no model component.
    from agentwatch.bom import _MODEL

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(agent=AgentIdentity(identity="a", name="triage"), tool=ToolCall(name="Bash"))
    )
    bom = build_bom(store)
    assert all(component.type != _MODEL for component in bom.components)


def test_none_observed_is_explicit(tmp_path: Path) -> None:
    # A session with no models and no MCP servers: components omitted, stated.
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record(
            agent=AgentIdentity(identity="a", name="triage"),
            tool=ToolCall(name="Bash"),
            harness=None,
        )
    )
    document = to_cyclonedx(build_bom(store))
    props = {p["name"]: p["value"] for p in document["metadata"]["properties"]}

    assert props["agentwatch:models"] == "none observed"
    assert props["agentwatch:mcp-servers"] == "none observed"


def test_agentwatch_json_has_top_level_coverage(tmp_path: Path) -> None:
    document = to_agentwatch_json(build_bom(_store(tmp_path)))

    assert document["format"] == "agentwatch-bom/1"
    assert document["coverage"]["basis"] == "observed"


def test_cli_bom_emits_and_audits_access(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(["--set", f"store.path={store_dir}", "bom", "--format", "cyclonedx"])

    assert rc == 0
    document = json.loads(capsys.readouterr().out)
    assert document["bomFormat"] == "CycloneDX"

    store = RecordStore(store_dir / "records.jsonl")
    accesses = store_accesses(store)
    assert [a.command for a in accesses] == ["bom"]


def test_cli_bom_session_scope(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir)
    store.append(_record(session="s2"))

    rc = main(["--set", f"store.path={store_dir}", "bom", "--session-id", "s1", "--format", "json"])

    assert rc == 0
    document = json.loads(capsys.readouterr().out)
    assert document["coverage"]["sessions"] == ["s1"]
