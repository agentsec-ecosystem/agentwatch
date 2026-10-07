"""Signed A2A agent-card provenance tests (M29 A2A-2 #365, PRD 45, ADR-0025).

Card-signature verification is a deterministic, local check whose *outcome* is
recorded (``verified``/``unverified``) — never assumed, never an authorization.
Keys come from an explicit mapping or the local ``AGENTWATCH_A2A_JWKS`` file; no
network, no LLM.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agentwatch import agent_card
from agentwatch.adapters import a2a_proxy


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _keypair() -> tuple[Ed25519PrivateKey, bytes, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public, agent_card.key_id(public)


def _sign(card: dict[str, Any], private: Ed25519PrivateKey, kid: str) -> dict[str, Any]:
    payload = agent_card.canonical_bytes(card)
    protected = _b64url(json.dumps({"alg": "EdDSA", "kid": kid}).encode())
    signature = private.sign(f"{protected}.{_b64url(payload)}".encode("ascii"))
    return {**card, "signatures": [{"protected": protected, "signature": _b64url(signature)}]}


def _base_card() -> dict[str, Any]:
    return {
        "name": "Remote Scheduler",
        "url": "https://scheduler.acme.example/a2a",
        "version": "1.0.0",
        "provider": {"organization": "Acme"},
    }


def test_verified_card_records_a_verified_outcome() -> None:
    private, public, kid = _keypair()
    card = _sign(_base_card(), private, kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: public})

    assert provenance.outcome == "verified"
    assert provenance.reason == "signature-valid"
    assert provenance.key_id == kid
    assert provenance.alg == "EdDSA"
    assert provenance.agent == "Remote Scheduler"
    assert provenance.org == "Acme"
    assert len(provenance.card_digest) == 64


def test_signature_with_an_unknown_key_is_unverified() -> None:
    private, _public, kid = _keypair()
    card = _sign(_base_card(), private, kid)

    provenance = agent_card.verify_agent_card(card, keys={})

    assert provenance.outcome == "unverified"
    assert provenance.reason == "key-unavailable"
    assert provenance.key_id == kid


def test_tampered_card_is_unverified() -> None:
    private, public, kid = _keypair()
    card = _sign(_base_card(), private, kid)
    card["name"] = "Tampered"

    provenance = agent_card.verify_agent_card(card, keys={kid: public})

    assert provenance.outcome == "unverified"
    assert provenance.reason == "signature-invalid"


def test_unsigned_card_is_unverified() -> None:
    provenance = agent_card.verify_agent_card(_base_card(), keys={})

    assert provenance.outcome == "unverified"
    assert provenance.reason == "unsigned"


def test_unsupported_algorithm_is_unverified() -> None:
    card = {**_base_card(), "signatures": [{"protected": "e30", "signature": "AAAA"}]}

    provenance = agent_card.verify_agent_card(card, keys={})

    assert provenance.outcome == "unverified"
    assert provenance.reason == "unsupported-alg"


def test_card_digest_is_stable_and_ignores_signatures() -> None:
    private, _public, kid = _keypair()
    card = _sign(_base_card(), private, kid)

    assert agent_card.card_digest(card) == agent_card.card_digest(_base_card())
    assert agent_card.card_digest(card) == agent_card.card_digest(
        {**_base_card(), "signatures": []}
    )


def test_keys_are_loaded_from_the_local_jwks_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, public, kid = _keypair()
    card = _sign(_base_card(), private, kid)
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps({"keys": {kid: _b64url(public)}}))
    monkeypatch.setenv(agent_card.KEYS_ENV, str(jwks))

    provenance = agent_card.verify_agent_card(card)

    assert provenance.outcome == "verified"
    assert provenance.key_id == kid


def test_card_record_records_the_verification_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, public, kid = _keypair()
    card = _sign(_base_card(), private, kid)
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps({"keys": {kid: _b64url(public)}}))
    monkeypatch.setenv(agent_card.KEYS_ENV, str(jwks))

    message = {
        "phase": "a2a",
        "harness": "a2a-proxy",
        "event": {
            "agent": "remote-scheduler",
            "session_id": "s-1",
            "direction": "card",
            "card": card,
            "source": "server",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }
    record = a2a_proxy.normalize(message)[0]

    assert record.tool.arguments is not None
    assert record.tool.arguments["outcome"] == "verified"
    assert record.tool.arguments["key_id"] == kid
    assert record.environment is not None
    assert record.environment["a2a"]["card"]["outcome"] == "verified"
    # A verification outcome is evidence, never an authorization verdict.
    assert record.authorization is None
    assert record.approval is None


def test_unverified_card_is_recorded_as_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(agent_card.KEYS_ENV, str(tmp_path / "missing.json"))
    message = {
        "phase": "a2a",
        "harness": "a2a-proxy",
        "event": {
            "agent": "remote-scheduler",
            "session_id": "s-1",
            "direction": "card",
            "card": _base_card(),
            "source": "server",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    }
    record = a2a_proxy.normalize(message)[0]

    assert record.tool.arguments["outcome"] == "unverified"
    assert record.tool.arguments["reason"] == "unsigned"
    assert record.authorization is None