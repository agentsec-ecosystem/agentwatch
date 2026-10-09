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
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
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

    assert record.tool.arguments is not None
    assert record.tool.arguments["outcome"] == "unverified"
    assert record.tool.arguments["reason"] == "unsigned"
    assert record.authorization is None


# ---------------------------------------------------------------------------
# Key formats + malformed inputs (deterministic, no network)
# ---------------------------------------------------------------------------


def _uint(value: int) -> str:
    return _b64url(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def _der(public: Any) -> bytes:
    return cast(
        bytes,
        public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def _pem(public: Any) -> str:
    return cast(
        str,
        public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii"),
    )


def _sign_generic(
    card: dict[str, Any], private: Any, alg: str, kid: str
) -> dict[str, Any]:
    payload = agent_card.canonical_bytes(card)
    protected = _b64url(json.dumps({"alg": alg, "kid": kid}).encode())
    signing_input = f"{protected}.{_b64url(payload)}".encode("ascii")
    if alg == "ES256":
        signature = private.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    elif alg == "RS256":
        signature = private.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    else:
        signature = private.sign(signing_input)
    return {**card, "signatures": [{"protected": protected, "signature": _b64url(signature)}]}


def test_verified_via_an_okp_jwk() -> None:
    private, public, kid = _keypair()
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": _b64url(public)}
    card = _sign_generic(_base_card(), private, "EdDSA", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: jwk})

    assert provenance.outcome == "verified"


def test_verified_via_an_ec_jwk() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    kid = agent_card.key_id(_der(public))
    numbers = public.public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(numbers.x.to_bytes(32, "big")),
        "y": _b64url(numbers.y.to_bytes(32, "big")),
    }
    card = _sign_generic(_base_card(), private, "ES256", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: jwk})

    assert provenance.outcome == "verified"


def test_verified_via_an_rsa_jwk() -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    kid = agent_card.key_id(_der(public))
    numbers = public.public_numbers()
    jwk = {"kty": "RSA", "n": _uint(numbers.n), "e": _uint(numbers.e)}
    card = _sign_generic(_base_card(), private, "RS256", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: jwk})

    assert provenance.outcome == "verified"


def test_verified_via_a_pem_string_key() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    kid = agent_card.key_id(_der(public))
    card = _sign_generic(_base_card(), private, "ES256", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: _pem(public)})

    assert provenance.outcome == "verified"


def test_verified_via_a_pem_bytes_key() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    kid = agent_card.key_id(_der(public))
    pem_bytes = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    card = _sign_generic(_base_card(), private, "ES256", kid)

    assert agent_card.verify_agent_card(card, keys={kid: pem_bytes}).outcome == "verified"


def test_wrong_key_type_for_algorithm_is_invalid() -> None:
    private, public, kid = _keypair()
    payload = agent_card.canonical_bytes(_base_card())
    protected = _b64url(json.dumps({"alg": "RS256", "kid": kid}).encode())
    signing_input = f"{protected}.{_b64url(payload)}".encode("ascii")
    signature = private.sign(signing_input)
    card = {
        **_base_card(),
        "signatures": [{"protected": protected, "signature": _b64url(signature)}],
    }

    # The JWK resolves to an Ed25519 key but the header claims RS256.
    provenance = agent_card.verify_agent_card(
        card, keys={kid: {"kty": "OKP", "crv": "Ed25519", "x": _b64url(public)}}
    )
    assert provenance.outcome == "unverified"
    assert provenance.reason == "signature-invalid"


def test_signed_card_without_keys_or_env_is_key_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)
    monkeypatch.delenv(agent_card.KEYS_ENV, raising=False)

    provenance = agent_card.verify_agent_card(card)

    assert provenance.reason == "key-unavailable"


def test_signed_card_with_an_unreadable_keys_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)
    monkeypatch.setenv(agent_card.KEYS_ENV, str(tmp_path / "missing.json"))

    provenance = agent_card.verify_agent_card(card)

    assert provenance.reason == "key-unavailable"


def test_unparseable_string_key_is_key_invalid() -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: "a"})

    assert provenance.reason == "key-invalid"


def test_unsupported_key_spec_is_key_invalid() -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: 1234})

    assert provenance.reason == "key-invalid"


def test_unknown_jwk_key_type_is_key_invalid() -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)

    provenance = agent_card.verify_agent_card(card, keys={kid: {"kty": "oct"}})

    assert provenance.reason == "key-invalid"


@pytest.mark.parametrize(
    "signatures",
    [
        [123],
        [{"protected": 1, "signature": "x"}],
        [{"protected": "!!!not-base64", "signature": "x"}],
    ],
)
def test_malformed_signatures_are_unverified(signatures: list[Any]) -> None:
    provenance = agent_card.verify_agent_card(
        {**_base_card(), "signatures": signatures}, keys={}
    )

    assert provenance.outcome == "unverified"
    assert provenance.reason == "malformed-signature"


def test_no_keys_and_no_env_is_unsigned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(agent_card.KEYS_ENV, raising=False)

    provenance = agent_card.verify_agent_card(_base_card())

    assert provenance.outcome == "unverified"
    assert provenance.reason == "unsigned"


def test_keys_file_without_a_keys_mapping_yields_no_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, _public, kid = _keypair()
    card = _sign_generic(_base_card(), private, "EdDSA", kid)
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps([1, 2, 3]))
    monkeypatch.setenv(agent_card.KEYS_ENV, str(jwks))

    provenance = agent_card.verify_agent_card(card)

    assert provenance.outcome == "unverified"
    assert provenance.reason == "key-unavailable"


def test_card_provenance_to_dict_round_trips() -> None:
    provenance = agent_card.verify_agent_card(_base_card(), keys={})
    assert provenance.to_dict()["outcome"] == "unverified"
    assert set(provenance.to_dict()) == {
        "outcome",
        "reason",
        "card_digest",
        "agent",
        "org",
        "key_id",
        "alg",
    }