"""Agent-identity privacy policy tests (M25 IDN-1, #299).

Confirms the two hard rules: principals are hashed by default (plaintext only in
``full``), and no identity field ever carries secret material.
"""

from __future__ import annotations

from agentwatch.adapters.claude_code import identity_for
from agentwatch.identity import (
    IDENTITY_HASH_PREFIX,
    apply_identity_privacy,
    hash_principal,
    identity_secret_kinds,
)
from agentwatch.records import AgentIdentity, CredentialClass, RecordPrivacyMode

KEY = b"per-install-test-key"


def _identity(**overrides: object) -> AgentIdentity:
    base: dict[str, object] = {
        "identity": "agent-1",
        "name": "triage",
        "principal": "alice@example.com",
        "delegation_chain": ("alice@example.com", "agent-1"),
        "workload_identity": "spiffe://corp.example/agent/triage",
        "credential_class": CredentialClass.SVID,
    }
    base.update(overrides)
    return AgentIdentity(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- hashing


def test_hash_principal_is_deterministic_and_never_plaintext() -> None:
    first = hash_principal("alice@example.com", key=KEY)
    second = hash_principal("alice@example.com", key=KEY)

    assert first == second
    assert first.startswith(IDENTITY_HASH_PREFIX)
    assert "alice" not in first


def test_hash_principal_is_keyed() -> None:
    assert hash_principal("alice", key=b"k1") != hash_principal("alice", key=b"k2")


def test_hash_principal_empty_is_empty() -> None:
    assert hash_principal("   ", key=KEY) == ""


# --------------------------------------------------------------------------- policy


def test_metadata_only_hashes_principal_and_chain() -> None:
    result = apply_identity_privacy(_identity(), mode=RecordPrivacyMode.METADATA_ONLY, key=KEY)

    assert result.principal is not None and result.principal.startswith(IDENTITY_HASH_PREFIX)
    assert result.delegation_chain is not None
    assert all(entry.startswith(IDENTITY_HASH_PREFIX) for entry in result.delegation_chain)
    # Non-principal identity fields are untouched.
    assert result.workload_identity == "spiffe://corp.example/agent/triage"
    assert result.credential_class is CredentialClass.SVID


def test_full_mode_keeps_plaintext_principal() -> None:
    result = apply_identity_privacy(_identity(), mode=RecordPrivacyMode.FULL, key=KEY)

    assert result.principal == "alice@example.com"
    assert result.delegation_chain == ("alice@example.com", "agent-1")


def test_absent_principals_stay_absent() -> None:
    result = apply_identity_privacy(
        AgentIdentity(identity="a"), mode=RecordPrivacyMode.METADATA_ONLY, key=KEY
    )

    assert result.principal is None
    assert result.delegation_chain is None


def test_secrets_are_masked_even_in_full_mode() -> None:
    leaked = "github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz0123456789"
    agent = _identity(principal=leaked, delegation_chain=(leaked,))

    for mode in (RecordPrivacyMode.METADATA_ONLY, RecordPrivacyMode.FULL):
        result = apply_identity_privacy(agent, mode=mode, key=KEY)
        assert leaked not in (result.principal or "")
        assert leaked not in "".join(result.delegation_chain or ())


def test_identity_secret_kinds_detects_planted_secret() -> None:
    leaked = "AKIAIOSFODNN7EXAMPLE"
    kinds = identity_secret_kinds(_identity(workload_identity=leaked))
    assert kinds


# --------------------------------------------------------------------------- property


def test_no_secret_survives_the_policy_property() -> None:
    from hypothesis import given
    from hypothesis import strategies as st

    @given(st.text(max_size=64), st.text(max_size=64))
    def _check(principal: str, chain_entry: str) -> None:
        agent = _identity(principal=principal, delegation_chain=(chain_entry,))
        result = apply_identity_privacy(agent, mode=RecordPrivacyMode.METADATA_ONLY, key=KEY)
        # The policy never leaves secret material behind.
        assert identity_secret_kinds(result) == ()
        # A non-empty principal is never stored in the clear.
        if principal.strip():
            assert result.principal != principal
            assert result.principal is not None
            assert result.principal.startswith(IDENTITY_HASH_PREFIX)

    _check()


# --------------------------------------------------------------------------- adapter wiring


def test_identity_for_populates_and_hashes_the_dimension() -> None:
    event = {
        "agent_id": "sub-1",
        "principal": "bob@example.com",
        "workload_identity": "spiffe://corp.example/agent/sub",
        "credential_class": "oauth",
        "delegation_chain": ["bob@example.com", "sub-1"],
    }

    agent = identity_for(event)

    assert agent.workload_identity == "spiffe://corp.example/agent/sub"
    assert agent.credential_class is CredentialClass.OAUTH
    assert agent.principal is not None and agent.principal.startswith(IDENTITY_HASH_PREFIX)
    assert all(entry.startswith(IDENTITY_HASH_PREFIX) for entry in agent.delegation_chain or ())


def test_identity_for_absent_dimension_stays_unknown() -> None:
    agent = identity_for({"agent_id": "sub-1"})

    assert agent.principal is None
    assert agent.workload_identity is None
    assert agent.credential_class is None
    assert agent.delegation_chain is None


def test_identity_for_rejects_unknown_credential_class() -> None:
    agent = identity_for({"agent_id": "sub-1", "credential_class": "magic"})

    assert agent.credential_class is None