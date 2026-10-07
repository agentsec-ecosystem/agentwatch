"""Fleet role x data-class access model + self-visible access log (M29 ACC-1, #448).

PRD 56 §ACC-1: a documented, enforceable read-access model (self / team reviewer /
security auditor / admin x metadata / identity-hashed / identity-resolved / content /
evidence). A cross-role read returns **nothing** and is itself recorded as a
``store-access`` record; a user can see, from their own machine, who accessed their
records; identity resolution is an explicit, recorded action; the default fleet
profile stores no content and hashes identity.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.access import (
    ACCESS_COMMANDS,
    ACCESS_MATRIX,
    DEFAULT_FLEET_PROFILE,
    DataClass,
    Role,
    access_log,
    evaluate_access,
    fleet_profile_from_config,
    matrix_to_json,
    read_fields,
    render_access_log,
    render_matrix,
    resolve_identity,
)
from agentwatch.cli.main import main
from agentwatch.configuration import AgentwatchConfig, PrivacySection
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import RecordStore
from agentwatch.store_access import STORE_ACCESS_TOOL

START = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _record(
    *,
    session: str = "s1",
    principal: str = "hmac-sha256:abc",
    mode: RecordPrivacyMode = RecordPrivacyMode.METADATA_ONLY,
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent", principal=principal),
        tool=ToolCall(name="Bash", arguments={"command": "ls"}, privacy_mode=mode),
        outcome=Outcome.OK,
        started_at=START,
        host="host-a",
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    return store


# --------------------------------------------------------------------------- matrix


def test_access_matrix_covers_every_role_and_data_class() -> None:
    assert [role.value for role in Role] == [
        "self",
        "team-reviewer",
        "security-auditor",
        "admin",
    ]
    assert [data.value for data in DataClass] == [
        "metadata",
        "identity-hashed",
        "identity-resolved",
        "content",
        "evidence",
    ]
    for role in Role:
        assert set(ACCESS_MATRIX[role]) == set(DataClass)


def test_default_fleet_profile_is_least_privileged() -> None:
    profile = DEFAULT_FLEET_PROFILE

    assert profile.privacy_mode == "metadata-only"
    assert profile.stores_content is False
    assert profile.hashes_identity is True


def test_team_reviewer_cannot_see_resolved_identity() -> None:
    decision = evaluate_access(
        Role.TEAM_REVIEWER,
        DataClass.IDENTITY_RESOLVED,
        owner="alice",
        reader="bob",
        same_team=True,
    )

    assert decision.allowed is False
    assert "identity-resolved" in decision.reason or "resolution" in decision.reason


# --------------------------------------------------------------------------- reads


def test_cross_role_read_returns_nothing_and_is_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = read_fields(
        store,
        store.records()[0],
        role=Role.TEAM_REVIEWER,
        data_class=DataClass.IDENTITY_RESOLVED,
        owner="alice",
        reader="bob",
    )

    assert result.fields == {}
    assert result.decision.allowed is False

    log = access_log(store, owner="alice")
    assert len(log) == 1
    assert log[0].reader == "bob"
    assert log[0].role is Role.TEAM_REVIEWER
    assert log[0].allowed is False
    assert store.verify().ok
    assert any(record.tool.name == STORE_ACCESS_TOOL for record in store.records())


def test_permitted_cross_user_metadata_read_is_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="bob",
    )

    assert result.decision.allowed is True
    assert result.fields["tool"] == "Bash"
    assert result.fields["session_id"] == "s1"

    log = access_log(store, owner="alice")
    assert len(log) == 1
    assert log[0].allowed is True
    assert log[0].data_class is DataClass.METADATA


def test_content_is_denied_when_the_mode_stores_no_content(tmp_path: Path) -> None:
    store = _store(tmp_path)

    denied = read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.CONTENT,
        owner="alice",
        reader="bob",
        content_available=False,
    )
    allowed = read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.CONTENT,
        owner="alice",
        reader="bob",
        content_available=True,
    )

    assert denied.fields == {}
    assert denied.decision.allowed is False
    assert allowed.decision.allowed is True
    assert allowed.fields["arguments"] == {"command": "ls"}


def test_plain_read_cannot_resolve_identity(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = read_fields(
        store,
        store.records()[0],
        role=Role.ADMIN,
        data_class=DataClass.IDENTITY_RESOLVED,
        owner="alice",
        reader="bob",
    )

    assert result.fields == {}
    assert result.decision.allowed is False


def test_owner_reads_their_own_record_without_an_access_record(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = read_fields(
        store,
        store.records()[0],
        role=Role.SELF,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="alice",
    )

    assert result.decision.allowed is True
    assert result.fields["tool"] == "Bash"
    assert access_log(store, owner="alice") == []


# --------------------------------------------------------------------------- resolve


def test_identity_resolution_is_an_explicit_recorded_action(tmp_path: Path) -> None:
    store = _store(tmp_path)

    permitted = resolve_identity(
        store,
        role=Role.SECURITY_AUDITOR,
        owner="alice",
        reader="bob",
        handle="hmac-sha256:abc",
        resolved="alice@corp.example",
    )
    refused = resolve_identity(
        store,
        role=Role.TEAM_REVIEWER,
        owner="alice",
        reader="carol",
        handle="hmac-sha256:abc",
        resolved="alice@corp.example",
    )

    assert permitted.fields == {
        "handle": "hmac-sha256:abc",
        "resolved": "alice@corp.example",
    }
    assert refused.fields == {}

    log = access_log(store, owner="alice")
    assert [entry.action for entry in log] == ["resolve-identity", "resolve-identity"]
    assert [entry.allowed for entry in log] == [True, False]
    assert store.verify().ok


# --------------------------------------------------------------------------- log


def test_access_log_is_scoped_to_the_owner(tmp_path: Path) -> None:
    store = _store(tmp_path)

    read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="bob",
        now=START,
    )
    read_fields(
        store,
        store.records()[0],
        role=Role.ADMIN,
        data_class=DataClass.METADATA,
        owner="carol",
        reader="dave",
        now=START,
    )

    log = access_log(store, owner="alice")

    assert [(entry.reader, entry.role.value) for entry in log] == [("bob", "security-auditor")]
    assert log[0].at == START


# --------------------------------------------------------------------------- cli


def test_fleet_profile_from_config_tracks_privacy_mode() -> None:
    default = fleet_profile_from_config(AgentwatchConfig())
    assert default == DEFAULT_FLEET_PROFILE
    assert default.to_dict()["stores_content"] is False

    full = fleet_profile_from_config(
        replace(AgentwatchConfig(), privacy=PrivacySection(mode="full"))
    )
    assert full.name == "extended"
    assert full.stores_content is True
    assert full.hashes_identity is False
    assert full.identity == "plaintext"


def test_self_role_has_no_cross_user_grant() -> None:
    decision = evaluate_access(Role.SELF, DataClass.METADATA, owner="alice", reader="bob")

    assert decision.allowed is False
    assert decision.to_dict()["cross_user"] is True


def test_team_reviewer_content_and_evidence_are_team_scoped() -> None:
    content = evaluate_access(
        Role.TEAM_REVIEWER,
        DataClass.CONTENT,
        owner="alice",
        reader="bob",
        content_available=True,
    )
    evidence = evaluate_access(Role.TEAM_REVIEWER, DataClass.EVIDENCE, owner="alice", reader="bob")
    same_team = evaluate_access(
        Role.TEAM_REVIEWER,
        DataClass.CONTENT,
        owner="alice",
        reader="bob",
        content_available=True,
        same_team=True,
    )

    assert content.allowed is False
    assert evidence.allowed is False
    assert same_team.allowed is True


def test_identity_hashed_projection_and_owner_content_gate(tmp_path: Path) -> None:
    store = _store(tmp_path)

    hashed = read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.IDENTITY_HASHED,
        owner="alice",
        reader="bob",
    )
    own_content = evaluate_access(
        Role.SELF, DataClass.CONTENT, owner="alice", reader="alice", content_available=False
    )

    assert hashed.fields["principal"] == "hmac-sha256:abc"
    assert own_content.allowed is False


def test_unknown_access_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown access action"):
        evaluate_access(Role.ADMIN, DataClass.METADATA, owner="a", reader="b", action="bogus")


def test_resolve_action_only_applies_to_identity_resolved() -> None:
    decision = evaluate_access(
        Role.ADMIN, DataClass.METADATA, owner="alice", reader="bob", action="resolve-identity"
    )

    assert decision.allowed is False


def test_render_helpers_are_publishable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="bob",
        now=START,
    )

    assert "READER" in render_access_log("alice", access_log(store, owner="alice"))
    assert "0 access(es)" in render_access_log("nobody", [])
    assert "security-auditor" in render_matrix()
    assert matrix_to_json()["admin"]["content"] is True
    assert set(ACCESS_COMMANDS) == {"access-read", "access-resolve"}


def test_cli_access_matrix_and_text_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir)
    read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="bob",
        now=START,
    )

    rc = main(["--set", f"store.path={store_dir}", "access", "matrix"])
    assert rc == 0
    assert "team-reviewer" in capsys.readouterr().out

    rc = main(["--set", f"store.path={store_dir}", "access", "matrix", "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["self"]["metadata"] is False

    rc = main(["--set", f"store.path={store_dir}", "access", "log", "--owner", "alice"])
    assert rc == 0
    assert "READER" in capsys.readouterr().out


def test_cli_access_log_json_lists_who_accessed_my_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir)
    read_fields(
        store,
        store.records()[0],
        role=Role.SECURITY_AUDITOR,
        data_class=DataClass.METADATA,
        owner="alice",
        reader="bob",
    )

    rc = main(["--set", f"store.path={store_dir}", "access", "log", "--owner", "alice", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["owner"] == "alice"
    assert payload["accesses"][0]["role"] == "security-auditor"
    assert payload["accesses"][0]["reader"] == "bob"
    assert payload["accesses"][0]["allowed"] is True


def test_cli_access_check_denied_returns_nonzero_and_is_logged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "access",
            "check",
            "--role",
            "team-reviewer",
            "--data-class",
            "identity-resolved",
            "--owner",
            "alice",
            "--reader",
            "bob",
        ]
    )

    assert rc != 0
    capsys.readouterr()
    store = RecordStore(store_dir / "records.jsonl")
    log = access_log(store, owner="alice")
    assert len(log) == 1
    assert log[0].allowed is False
