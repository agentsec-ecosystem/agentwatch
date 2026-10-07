"""Authorization provenance v2 taxonomy + legacy mapping (M29 APV-1, #438).

Every value has a derivation fixture; the legacy S14 five-value ``approval``
maps at read time (never written back); and ``outcome=ok`` never implies
consent. ``unknown`` is the honest default.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from agentwatch.adapters import claude_code
from agentwatch.authorization import (
    AUTHORIZATION_TAXONOMY_VERSION,
    authorization_from_decision_source,
    derive_authorization,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Approval,
    Authorization,
    AuthorizationDeny,
    AuthorizationEvidence,
    AuthorizationSource,
    Outcome,
    ToolCall,
    effective_authorization,
    validate_record,
)


def _record(
    *, approval: Approval | None, authorization: Authorization | None = None
) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        approval=approval,
        authorization=authorization,
    )


def test_taxonomy_version_is_pinned() -> None:
    assert AUTHORIZATION_TAXONOMY_VERSION == "authz-v2"


# --- every value has a derivation fixture ---------------------------------


@pytest.mark.parametrize(
    ("decision_source", "source", "deny"),
    [
        ("config", AuthorizationSource.RULE, None),
        ("hook", AuthorizationSource.HOOK, None),
        ("user_permanent", AuthorizationSource.HUMAN_REMEMBERED, None),
        ("user_temporary", AuthorizationSource.HUMAN_ONCE, None),
        ("reject", AuthorizationSource.DENIED, AuthorizationDeny.HUMAN),
        ("classifier", AuthorizationSource.CLASSIFIER, None),
    ],
)
def test_native_decision_source_fixture(
    decision_source: str, source: AuthorizationSource, deny: AuthorizationDeny | None
) -> None:
    auth = authorization_from_decision_source(decision_source)
    assert auth is not None
    assert auth.source is source
    assert auth.deny is deny
    assert auth.evidence is AuthorizationEvidence.HARNESS_NATIVE


def test_native_unknown_decision_source_is_none() -> None:
    assert authorization_from_decision_source("mystery") is None


def test_classifier_is_never_user_or_rule() -> None:
    auth = authorization_from_decision_source("classifier")
    assert auth is not None
    assert auth.source is AuthorizationSource.CLASSIFIER
    assert auth.source not in (AuthorizationSource.HUMAN_ONCE, AuthorizationSource.RULE)


def test_bypass_mode_when_no_more_specific_source() -> None:
    from agentwatch.records import PermissionMode

    auth = derive_authorization(
        approval=Approval.UNKNOWN, permission_mode=PermissionMode.BYPASS_PERMISSIONS
    )
    assert auth.source is AuthorizationSource.BYPASS
    assert auth.evidence is AuthorizationEvidence.SESSION_MODE


def test_native_source_beats_bypass_mode() -> None:
    from agentwatch.records import PermissionMode

    auth = derive_authorization(
        approval=Approval.UNKNOWN,
        decision_source="classifier",
        permission_mode=PermissionMode.BYPASS_PERMISSIONS,
    )
    assert auth.source is AuthorizationSource.CLASSIFIER


# --- legacy mapping at read time -------------------------------------------


@pytest.mark.parametrize(
    ("approval", "source", "deny"),
    [
        (Approval.USER, AuthorizationSource.HUMAN_ONCE, None),
        (Approval.AUTO, AuthorizationSource.RULE, None),
        (Approval.NOT_REQUIRED, AuthorizationSource.NOT_REQUIRED, None),
        (Approval.DENIED, AuthorizationSource.DENIED, AuthorizationDeny.UNKNOWN),
        (Approval.UNKNOWN, AuthorizationSource.UNKNOWN, None),
    ],
)
def test_legacy_approval_maps_at_read_time(
    approval: Approval, source: AuthorizationSource, deny: AuthorizationDeny | None
) -> None:
    record = _record(approval=approval)
    auth = effective_authorization(record)
    assert auth.source is source
    assert auth.deny is deny
    assert auth.evidence is AuthorizationEvidence.INFERRED


def test_legacy_value_is_never_written_back() -> None:
    record = _record(approval=Approval.USER)
    effective_authorization(record)
    assert "authorization" not in record.to_dict()


def test_stored_authorization_wins_over_legacy() -> None:
    stored = Authorization(
        source=AuthorizationSource.CLASSIFIER, evidence=AuthorizationEvidence.HARNESS_NATIVE
    )
    record = _record(approval=Approval.USER, authorization=stored)
    assert effective_authorization(record) == stored


def test_absent_authorization_reads_as_unknown() -> None:
    record = _record(approval=None)
    assert effective_authorization(record).source is AuthorizationSource.UNKNOWN


# --- never inferred from outcome=ok ----------------------------------------


def test_outcome_ok_is_never_consent() -> None:
    record = _record(approval=None)
    assert record.outcome is Outcome.OK
    assert effective_authorization(record).source is AuthorizationSource.UNKNOWN


def test_ok_pre_event_has_no_authorization_field() -> None:
    message: dict[str, Any] = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-ok",
            "tool_name": "Bash",
            "tool_use_id": "call-ok",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }
    (record,) = claude_code.normalize(message)
    assert record.outcome is Outcome.OK
    assert record.authorization is None
    assert effective_authorization(record).source is AuthorizationSource.UNKNOWN


# --- adapter attaches a native source --------------------------------------


def test_adapter_records_classifier_source() -> None:
    message: dict[str, Any] = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-c",
            "tool_name": "Bash",
            "tool_use_id": "call-c",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "tool_decision": {"decision_source": "classifier", "decision": "allow"},
        },
    }
    (record,) = claude_code.normalize(message)
    assert record.authorization is not None
    assert record.authorization.source is AuthorizationSource.CLASSIFIER
    assert record.authorization.evidence is AuthorizationEvidence.HARNESS_NATIVE
    validate_record(record.to_dict())


def test_adapter_records_bypass_without_prompt() -> None:
    message: dict[str, Any] = {
        "phase": "pre",
        "harness": "claude-code",
        "event": {
            "session_id": "sess-b",
            "tool_name": "Bash",
            "tool_use_id": "call-b",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "permission_mode": "bypassPermissions",
        },
    }
    (record,) = claude_code.normalize(message)
    assert record.authorization is not None
    assert record.authorization.source is AuthorizationSource.BYPASS


# --- schema round-trip ------------------------------------------------------


def test_authorization_object_round_trips_and_validates() -> None:
    stored = Authorization(
        source=AuthorizationSource.DENIED,
        deny=AuthorizationDeny.RULE,
        evidence=AuthorizationEvidence.HARNESS_NATIVE,
    )
    record = _record(approval=None, authorization=stored)
    payload = record.to_dict()
    assert payload["authorization"] == {
        "source": "denied",
        "deny": "rule",
        "evidence": "harness-native",
    }
    validate_record(payload)
    assert AgentRecord.from_dict(payload).authorization == stored


def test_authorization_rejects_unknown_source() -> None:
    record = _record(approval=None)
    payload = record.to_dict()
    payload["authorization"] = {"source": "not-a-source"}
    from agentwatch.records import RecordValidationError

    with pytest.raises(RecordValidationError):
        validate_record(payload)
