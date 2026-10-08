"""Capability inventory tests (M30 CAP-1, #458; PRD 52).

Skills, plugins, hooks, subagents/commands, rules files, MCP servers and (later)
memory are inventoried by **content digest**, never by declared version. The
inventory is metadata only: names, origin scope, digests and sizes — content is
read to hash it and then discarded, never retained.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.capabilities import (
    CAP_KIND_COMMAND,
    CAP_KIND_HOOK,
    CAP_KIND_MCP,
    CAP_KIND_MEMORY,
    CAP_KIND_PLUGIN,
    CAP_KIND_RULES,
    CAP_KIND_SKILL,
    CAP_KIND_SUBAGENT,
    COVERAGE_EXPOSED,
    COVERAGE_NONE,
    SCOPE_PROJECT,
    SCOPE_USER,
    Capability,
    capabilities_to_json,
    discover_capabilities,
)
from agentwatch.cli.main import main


def _seed_claude_home(home: Path) -> None:
    claude = home / ".claude"
    (claude / "skills" / "pdf").mkdir(parents=True, exist_ok=True)
    (claude / "skills" / "pdf" / "SKILL.md").write_text("---\nname: pdf\n---\nbody\n")

    plugin = claude / "plugins" / "demo" / ".claude-plugin"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "plugin.json").write_text('{"name": "demo", "version": "1.2.3"}')
    (plugin.parent / "plugin.py").write_text("print('demo')\n")

    (claude / "agents").mkdir(parents=True, exist_ok=True)
    (claude / "agents" / "reviewer.md").write_text("reviewer agent\n")

    (claude / "commands").mkdir(parents=True, exist_ok=True)
    (claude / "commands" / "fix.md").write_text("fix command\n")

    (claude / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "/bin/evil"}]}
                    ]
                }
            }
        )
    )
    (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"github": {"command": "npx", "args": ["-y", "gh"]}}})
    )


def _seed_project(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "CLAUDE.md").write_text("project rules\n")
    (project / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (project / ".claude" / "rules" / "r.md").write_text("a rule\n")
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"db": {"command": "db-server"}}})
    )


def _inventory(tmp_path: Path):  # type: ignore[no-untyped-def]
    home = tmp_path / "home"
    project = tmp_path / "project"
    _seed_claude_home(home)
    _seed_project(project)
    return discover_capabilities(project=project, home=home)


def test_inventory_lists_every_kind_with_scope_and_digest(tmp_path: Path) -> None:
    inv = _inventory(tmp_path)
    by_kind: dict[str, list[Capability]] = {}
    for capability in inv.capabilities:
        by_kind.setdefault(capability.kind, []).append(capability)

    for kind in (
        CAP_KIND_SKILL,
        CAP_KIND_PLUGIN,
        CAP_KIND_HOOK,
        CAP_KIND_SUBAGENT,
        CAP_KIND_COMMAND,
        CAP_KIND_RULES,
        CAP_KIND_MCP,
    ):
        assert by_kind[kind], f"missing {kind}"
        assert all(cap.digest for cap in by_kind[kind])

    skill = by_kind[CAP_KIND_SKILL][0]
    assert skill.name == "pdf"
    assert skill.scope == SCOPE_USER
    assert len(skill.digest) == 64

    plugin = by_kind[CAP_KIND_PLUGIN][0]
    assert plugin.name == "demo"
    assert plugin.declared_version == "1.2.3"

    rules_scopes = {cap.scope for cap in by_kind[CAP_KIND_RULES]}
    assert rules_scopes == {SCOPE_PROJECT}

    hook = by_kind[CAP_KIND_HOOK][0]
    assert hook.scope == SCOPE_USER

    mcp_scopes = {cap.scope for cap in by_kind[CAP_KIND_MCP]}
    assert mcp_scopes == {SCOPE_USER, SCOPE_PROJECT}


def test_digest_follows_content_not_declared_version(tmp_path: Path) -> None:
    """The Plugin4Shell shape: same name+version, different content -> new digest."""
    home = tmp_path / "home"
    _seed_claude_home(home)
    project = tmp_path / "project"
    _seed_project(project)

    before = discover_capabilities(project=project, home=home)
    first = next(c for c in before.capabilities if c.kind == CAP_KIND_PLUGIN)
    assert first.declared_version == "1.2.3"

    (home / ".claude" / "plugins" / "demo" / "plugin.py").write_text("print('owned')\n")

    after = discover_capabilities(project=project, home=home)
    second = next(c for c in after.capabilities if c.kind == CAP_KIND_PLUGIN)

    assert second.declared_version == "1.2.3"
    assert second.digest != first.digest


def test_digest_is_stable_across_runs(tmp_path: Path) -> None:
    first = _inventory(tmp_path).capabilities
    second = _inventory(tmp_path).capabilities
    assert [(c.kind, c.name, c.digest) for c in first] == [
        (c.kind, c.name, c.digest) for c in second
    ]


def test_no_capability_content_is_retained(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _seed_claude_home(home)
    secret = "SUPERSECRET-TOKEN-1234567890"
    (home / ".claude" / "skills" / "pdf" / "SKILL.md").write_text(f"payload {secret}\n")
    project = tmp_path / "project"
    _seed_project(project)

    inv = discover_capabilities(project=project, home=home)
    rendered = json.dumps(capabilities_to_json(inv))

    assert secret not in rendered
    for capability in inv.capabilities:
        assert secret not in capability.to_dict().__repr__()


def test_coverage_declares_per_harness_gaps(tmp_path: Path) -> None:
    inv = _inventory(tmp_path)
    rows = {(row.harness, row.kind): row.status for row in inv.coverage}

    assert rows[("claude-code", CAP_KIND_SKILL)] == COVERAGE_EXPOSED
    assert rows[("claude-code", CAP_KIND_RULES)] == COVERAGE_EXPOSED
    assert rows[("cursor", CAP_KIND_SKILL)] == COVERAGE_NONE
    assert rows[("codex-cli", CAP_KIND_SKILL)] == COVERAGE_NONE
    assert rows[("gemini-cli", CAP_KIND_SKILL)] == COVERAGE_NONE


def test_bom_includes_capabilities_as_components(tmp_path: Path) -> None:
    from agentwatch.bom import build_bom
    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
    from agentwatch.store import RecordStore

    home = tmp_path / "home"
    _seed_claude_home(home)
    inv = discover_capabilities(project=None, home=home)

    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="agentwatch"),
            tool=ToolCall(name="Read"),
            outcome=Outcome.OK,
            started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
    )
    bom = build_bom(store, capabilities=inv.capabilities)

    names = {component.name for component in bom.components}
    assert "pdf" in names
    pdf = next(c for c in bom.components if c.name == "pdf")
    props = dict(pdf.properties)
    assert props["agentwatch:capability-kind"] == CAP_KIND_SKILL


def test_cli_inventory_capabilities_json(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    home = tmp_path / "home"
    _seed_claude_home(home)
    project = tmp_path / "project"
    _seed_project(project)
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    rc = main(
        ["--set", f"store.path={store_dir}", "inventory", "--capabilities", "--json"]
    )

    assert rc == 0


def test_size_reflects_content_bytes(tmp_path: Path) -> None:
    """Size is the summed byte length of the hashed content, never the content."""
    inv = _inventory(tmp_path)
    skill = next(c for c in inv.capabilities if c.kind == CAP_KIND_SKILL)
    assert skill.size == len("---\nname: pdf\n---\nbody\n")


def test_digest_changes_when_hook_command_changes(tmp_path: Path) -> None:
    """A hook is digested by its content, so a swapped command is a new digest."""
    home = tmp_path / "home"
    _seed_claude_home(home)
    project = tmp_path / "project"
    _seed_project(project)

    before = discover_capabilities(project=project, home=home)
    first = next(c for c in before.capabilities if c.kind == CAP_KIND_HOOK)

    (home / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "/bin/good"}]}
                    ]
                }
            }
        )
    )

    after = discover_capabilities(project=project, home=home)
    second = next(c for c in after.capabilities if c.kind == CAP_KIND_HOOK)
    assert second.name == first.name
    assert second.digest != first.digest


def test_missing_directories_yield_empty_inventory(tmp_path: Path) -> None:
    inv = discover_capabilities(project=tmp_path / "absent", home=tmp_path / "void")
    assert inv.capabilities == ()
    # Coverage is still declared: absence is a stated gap, not silence.
    harnesses = {"claude-code", "cursor", "codex-cli", "gemini-cli"}
    assert {row.harness for row in inv.coverage} == harnesses


def test_coverage_includes_the_memory_gap() -> None:
    inv = discover_capabilities(project=None, home=Path("/nonexistent-home-m30"))
    rows = {(row.harness, row.kind): row.status for row in inv.coverage}
    assert rows[("claude-code", CAP_KIND_MEMORY)] == COVERAGE_NONE
    assert rows[("claude-code", CAP_KIND_MCP)] == COVERAGE_EXPOSED


def test_json_carries_the_coverage_matrix_without_content(tmp_path: Path) -> None:
    inv = _inventory(tmp_path)
    document = capabilities_to_json(inv)
    assert document["capabilities"]
    assert {"harness", "kind", "status"} == set(document["coverage"][0])
    for entry in document["capabilities"]:
        assert set(entry) == {"kind", "name", "scope", "digest", "size", "declared_version"}


def test_cli_bom_carries_capability_components(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    home = tmp_path / "home"
    _seed_claude_home(home)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    rc = main(["--set", f"store.path={store_dir}", "bom", "--format", "cyclonedx"])

    assert rc == 0
