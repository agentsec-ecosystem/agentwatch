"""``suggest-policy`` + dangerous-broad lint (M30 POL-1, #469).

History is the only defensible source for a tighter policy, but agentwatch stays
monitor-only: the output is an inert file/diff, never applied. Every rule is
evidence-linked; destructive/network/credential-adjacent calls are never
suggested as ``allow`` by default; broad rules are linted; the run is
deterministic and writes nothing outside ``--out``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.cli.main import main
from agentwatch.policy_suggest import (
    FORMAT_VERSION,
    TARGETS,
    Rule,
    lint_rules,
    render_policy_suggestion,
    suggest_policy,
    suggestion_to_dict,
)
from agentwatch.records import AgentIdentity, AgentRecord, Approval, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    session: str,
    tool: str,
    *,
    arguments: dict[str, object] | None = None,
    outcome: Outcome = Outcome.OK,
    approval: Approval | None = None,
    at: datetime | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool, arguments=arguments),
        outcome=outcome,
        started_at=at or NOW,
        approval=approval,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record("s1", "Bash", arguments={"command": "ls"}, approval=Approval.AUTO, at=NOW)
    )
    store.append(
        _record(
            "s1",
            "Bash",
            arguments={"command": "curl https://example.invalid"},
            at=NOW - timedelta(days=1),
        )
    )
    store.append(_record("s2", "Bash", arguments={"command": "rm -rf /tmp/x"}, at=NOW))
    store.append(_record("s2", "Bash", arguments={"command": "cat ~/.aws/credentials"}, at=NOW))
    store.append(_record("s1", "Write", arguments={"file_path": "/tmp/out.txt"}, at=NOW))
    store.append(_record("s2", "Read", arguments={"file_path": "/tmp/in.txt"}, at=NOW))
    store.append(_record("s2", "Bash", outcome=Outcome.DENIED, at=NOW))
    return store


def _by_matcher(suggestion: object) -> dict[str, Rule]:
    return {rule.matcher: rule for rule in suggestion.rules}  # type: ignore[attr-defined]


# --- contract -----------------------------------------------------------------


def test_targets_are_the_documented_set() -> None:
    assert set(TARGETS) == {"claude-settings", "mcp-allowlist", "acs"}


def test_output_states_window_records_and_coverage_gaps(tmp_path: Path) -> None:
    suggestion = suggest_policy(_store(tmp_path), since="30d", target="claude-settings", now=NOW)
    assert suggestion.format_version == FORMAT_VERSION
    assert suggestion.window == "30d"
    assert suggestion.records == 7
    assert suggestion.coverage_gaps  # the metadata-only Bash has no captured program


def test_each_rule_is_evidence_linked(tmp_path: Path) -> None:
    suggestion = suggest_policy(_store(tmp_path), since="30d", target="claude-settings", now=NOW)
    for rule in suggestion.rules:
        assert rule.evidence.calls >= 1
        assert rule.evidence.sessions
        assert rule.evidence.last_seen is not None


# --- least privilege: never allow-by-default ----------------------------------


def test_destructive_network_and_credential_are_ask_not_allow(tmp_path: Path) -> None:
    suggestion = suggest_policy(_store(tmp_path), since="30d", target="claude-settings", now=NOW)
    rules = _by_matcher(suggestion)
    assert rules["Bash(rm:*)"].effect == "ask"
    assert rules["Bash(curl:*)"].effect == "ask"
    assert rules["Bash(cat:*)"].effect == "ask"
    # and they are annotated with the class that forced the downgrade
    assert "command:destructive" in rules["Bash(rm:*)"].categories
    assert rules["Bash(ls:*)"].effect == "allow"
    assert rules["Write"].effect == "allow"


def test_include_promotes_a_never_allow_class_to_allow(tmp_path: Path) -> None:
    suggestion = suggest_policy(
        _store(tmp_path), since="30d", target="claude-settings", include=True, now=NOW
    )
    assert _by_matcher(suggestion)["Bash(rm:*)"].effect == "allow"


# --- broad-rule lint -----------------------------------------------------------


def test_lint_flags_broad_interpreter_and_network_rules() -> None:
    broad_interpreter = Rule(
        id="tool:Bash",
        effect="ask",
        tool="Bash",
        matcher="Bash",
        categories=("unclassified",),
        rationale="unscoped shell",
    )
    broad_network = Rule(
        id="tool:Bash(curl)",
        effect="allow",
        tool="Bash",
        matcher="Bash(curl:*)",
        categories=("network:destination",),
        rationale="network",
    )
    findings = lint_rules([broad_interpreter, broad_network])
    kinds = {finding.kind for finding in findings}
    assert "interpreter/exec" in kinds
    assert "network" in kinds


def test_generated_suggestion_lints_its_unscoped_shell(tmp_path: Path) -> None:
    suggestion = suggest_policy(_store(tmp_path), since="30d", target="claude-settings", now=NOW)
    assert any(finding.kind == "interpreter/exec" for finding in suggestion.lint)


# --- determinism + rendering ---------------------------------------------------


def test_output_is_deterministic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = suggestion_to_dict(
        suggest_policy(store, since="30d", target="claude-settings", now=NOW)
    )
    second = suggestion_to_dict(
        suggest_policy(store, since="30d", target="claude-settings", now=NOW)
    )
    assert first == second
    assert json.dumps(first, sort_keys=True)


def test_render_mentions_advisory_and_target(tmp_path: Path) -> None:
    suggestion = suggest_policy(_store(tmp_path), since="30d", target="acs", now=NOW)
    text = render_policy_suggestion(suggestion)
    assert "advisory" in text.lower()
    assert "acs" in text


# --- CLI: no write outside --out ----------------------------------------------


def test_cli_writes_only_the_out_file(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    settings = home / ".claude" / "settings.json"
    settings.write_text('{"permissions": {"allow": ["Bash"]}}\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude").mkdir()
    project_settings = project / ".claude" / "settings.json"
    project_settings.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(project)

    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    out = project / "suggested.json"
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "suggest-policy",
            "--since",
            "30d",
            "--target",
            "claude-settings",
            "--out",
            str(out),
        ]
    )
    assert rc == 0

    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    added = set(after) - set(before)
    assert added == {Path("project/suggested.json")}
    changed = {key for key in before if before[key] != after[key]}
    assert changed == set()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["target"] == "claude-settings"
    assert "permissions" in payload["document"]


def test_cli_json_goes_to_stdout(tmp_path: Path, capsys) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)
    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "suggest-policy",
            "--since",
            "30d",
            "--target",
            "mcp-allowlist",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target"] == "mcp-allowlist"
