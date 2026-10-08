"""``what-if`` policy replay over history (M30 POL-2, #470).

Replaying a candidate policy over history is the confidence step before
enforcement: it reports allowed/asked/denied counts and the delta vs actual
behavior (prompts avoided, would-be denials with sessions, actual-authorization
differences). The output is a labeled simulation stamped with the policy-format
version; parse errors are explicit and unsupported syntax is reported.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.policy_suggest import (
    POLICY_FORMAT_VERSION,
    WHATIF_FORMAT_VERSION,
    PolicyParseError,
    parse_policy,
    render_whatif,
    simulate_policy,
    whatif_to_dict,
)
from agentwatch.records import AgentIdentity, AgentRecord, Approval, Outcome, ToolCall
from agentwatch.store import RecordStore

NOW = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

POLICY = {
    "format_version": POLICY_FORMAT_VERSION,
    "rules": [
        {"matcher": "Bash(ls:*)", "effect": "allow"},
        {"matcher": "Bash(rm:*)", "effect": "deny"},
        {"matcher": "Write", "effect": "ask"},
    ],
}


def _record(
    session: str,
    tool: str,
    *,
    arguments: dict[str, object] | None = None,
    approval: Approval = Approval.AUTO,
    outcome: Outcome = Outcome.OK,
    at: datetime = NOW,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool, arguments=arguments),
        outcome=outcome,
        started_at=at,
        approval=approval,
    )


def _store(tmp_path: Path, *, at: datetime = NOW) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(
        _record("s1", "Bash", arguments={"command": "ls"}, approval=Approval.USER, at=at)
    )
    store.append(_record("s1", "Bash", arguments={"command": "rm -rf /tmp/x"}, at=at))
    store.append(_record("s2", "Write", arguments={"file_path": "/tmp/o"}, at=at))
    store.append(
        _record("s2", "Bash", arguments={"command": "curl https://example.invalid"}, at=at)
    )
    return store


# --- parsing -------------------------------------------------------------------


def test_valid_policy_parses() -> None:
    policy = parse_policy(json.dumps(POLICY))
    assert policy.format_version == POLICY_FORMAT_VERSION
    assert [rule.matcher for rule in policy.rules] == [
        "Bash(ls:*)",
        "Bash(rm:*)",
        "Write",
    ]
    assert policy.unsupported == ()


def test_parse_errors_are_explicit() -> None:
    with pytest.raises(PolicyParseError, match="JSON"):
        parse_policy("{not json")
    with pytest.raises(PolicyParseError, match="format_version"):
        parse_policy(json.dumps({"rules": []}))
    with pytest.raises(PolicyParseError, match="rules"):
        parse_policy(json.dumps({"format_version": POLICY_FORMAT_VERSION}))
    with pytest.raises(PolicyParseError, match="matcher"):
        parse_policy(
            json.dumps(
                {"format_version": POLICY_FORMAT_VERSION, "rules": [{"effect": "allow"}]}
            )
        )
    with pytest.raises(PolicyParseError, match="effect"):
        parse_policy(
            json.dumps(
                {
                    "format_version": POLICY_FORMAT_VERSION,
                    "rules": [{"matcher": "Bash", "effect": "maybe"}],
                }
            )
        )


def test_unsupported_syntax_is_reported_not_guessed() -> None:
    policy = parse_policy(
        json.dumps(
            {
                "format_version": POLICY_FORMAT_VERSION,
                "rules": [{"matcher": "Bash(.*)", "effect": "allow"}],
            }
        )
    )
    assert policy.rules == ()
    assert policy.unsupported


# --- simulation ----------------------------------------------------------------


def test_counts_and_would_be_denials_and_prompts_avoided(tmp_path: Path) -> None:
    report = simulate_policy(
        _store(tmp_path), parse_policy(json.dumps(POLICY)), since="30d", now=NOW
    )

    assert report.counts == {"allow": 1, "ask": 2, "deny": 1}
    assert report.actual == {"allowed": 3, "prompted": 1, "denied": 0}

    assert len(report.prompts_avoided) == 1
    assert report.prompts_avoided[0]["session"] == "s1"

    assert len(report.would_be_denials) == 1
    denial = report.would_be_denials[0]
    assert denial["session"] == "s1"
    assert denial["tool"] == "Bash"
    assert denial["actual"] == "allow"

    # every call whose actual authorization differs from the policy is listed
    assert len(report.authorization_differences) == 4


def test_report_is_labeled_simulation_and_stamped(tmp_path: Path) -> None:
    report = simulate_policy(
        _store(tmp_path), parse_policy(json.dumps(POLICY)), since="30d", now=NOW
    )
    assert report.simulation is True
    assert report.policy_format_version == POLICY_FORMAT_VERSION
    assert report.format_version == WHATIF_FORMAT_VERSION
    assert report.window == "30d"
    assert report.records == 4
    assert "simulation" in render_whatif(report).lower()


def test_simulation_is_deterministic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    policy = parse_policy(json.dumps(POLICY))
    first = whatif_to_dict(simulate_policy(store, policy, since="30d", now=NOW))
    second = whatif_to_dict(simulate_policy(store, policy, since="30d", now=NOW))
    assert first == second


def test_unmatched_calls_default_to_ask(tmp_path: Path) -> None:
    report = simulate_policy(
        _store(tmp_path), parse_policy(json.dumps(POLICY)), since="30d", now=NOW
    )
    # curl is not in the policy and is therefore a prompt candidate, never silently allowed
    assert report.counts["ask"] == 2


# --- CLI -----------------------------------------------------------------------


def test_cli_what_if_emits_json_simulation(tmp_path: Path, capsys) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir, at=datetime.now(timezone.utc))
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(POLICY), encoding="utf-8")

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "what-if",
            str(policy_path),
            "--since",
            "30d",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["simulation"] is True
    assert payload["counts"] == {"allow": 1, "ask": 2, "deny": 1}


def test_cli_parse_error_is_explicit(tmp_path: Path, capsys) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)
    policy_path = tmp_path / "bad.json"
    policy_path.write_text("{not json", encoding="utf-8")

    rc = main(["--set", f"store.path={store_dir}", "what-if", str(policy_path)])

    assert rc != 0
    assert "policy" in capsys.readouterr().err.lower()
