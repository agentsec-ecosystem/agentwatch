"""A2A signed agent-card provenance (M29 A2A-2 #365, PRD 45, ADR-0025).

A2A v1.0 agent cards can carry a JWS ``signatures`` block: cryptographic
workload identity. agentwatch records the **verification outcome**
(``verified`` / ``unverified``) as evidence — never as an authorization, never
assumed, and never via an LLM. Verification is deterministic and local: keys
come from an explicit mapping or the local ``AGENTWATCH_A2A_JWKS`` file, and a
card whose key we do not hold is recorded ``unverified`` with a reason.

The JWS signing input follows RFC 7515: ``BASE64URL(protected) || "." ||
BASE64URL(JCS(card_without_signatures))``. Canonicalization is RFC 8785-style
(sorted keys, no whitespace); full JCS number-normalization is a documented gap.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature

KEYS_ENV = "AGENTWATCH_A2A_JWKS"

_SUPPORTED_ALGS = frozenset({"EdDSA", "ES256", "RS256"})

OUTCOME_VERIFIED = "verified"
OUTCOME_UNVERIFIED = "unverified"


@dataclass(frozen=True)
class CardProvenance:
    """The deterministic verification outcome recorded for one agent card."""

    outcome: str
    reason: str
    card_digest: str
    agent: str | None = None
    org: str | None = None
    key_id: str | None = None
    alg: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "card_digest": self.card_digest,
            "agent": self.agent,
            "org": self.org,
            "key_id": self.key_id,
            "alg": self.alg,
        }


def key_id(public_bytes: bytes) -> str:
    """A stable short id for a public key (metadata, not a secret)."""
    return hashlib.sha256(public_bytes).hexdigest()[:16]


def canonical_bytes(card: Mapping[str, Any]) -> bytes:
    """RFC 8785-style canonical bytes of a card without its ``signatures``."""
    without = {key: value for key, value in card.items() if key != "signatures"}
    return json.dumps(without, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def card_digest(card: Mapping[str, Any]) -> str:
    """A stable sha256 digest of a card (provenance, never content)."""
    return hashlib.sha256(canonical_bytes(card)).hexdigest()


def _card_identity(card: Mapping[str, Any]) -> tuple[str | None, str | None]:
    name = card.get("name")
    provider = card.get("provider")
    org = provider.get("organization") if isinstance(provider, Mapping) else None
    agent = name if isinstance(name, str) and name else None
    return agent, org if isinstance(org, str) and org else None


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _load_keys(keys: Mapping[str, Any] | None, keys_path: str | None) -> dict[str, Any]:
    """Resolve the key set from an explicit mapping or the local JWKS file."""
    if keys is not None:
        return dict(keys)
    path = keys_path or os.environ.get(KEYS_ENV)
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    raw = data.get("keys") if isinstance(data, Mapping) else None
    return dict(raw) if isinstance(raw, Mapping) else {}


def _public_key(spec: Any, alg: str) -> Any:
    """Coerce a raw key spec (raw bytes, base64url, PEM, or JWK) to a public key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256R1,
        EllipticCurvePublicNumbers,
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    if isinstance(spec, Mapping):  # a JWK
        kty = spec.get("kty")
        if kty == "OKP" and spec.get("crv") == "Ed25519":
            return Ed25519PublicKey.from_public_bytes(_b64url_decode(str(spec["x"])))
        if kty == "EC" and spec.get("crv") == "P-256":
            numbers = EllipticCurvePublicNumbers(
                int.from_bytes(_b64url_decode(str(spec["x"])), "big"),
                int.from_bytes(_b64url_decode(str(spec["y"])), "big"),
                SECP256R1(),
            )
            return numbers.public_key()
        if kty == "RSA":
            numbers = RSAPublicNumbers(
                int.from_bytes(_b64url_decode(str(spec["e"])), "big"),
                int.from_bytes(_b64url_decode(str(spec["n"])), "big"),
            )
            return numbers.public_key()
        raise ValueError("unsupported JWK")
    if isinstance(spec, str):
        try:
            raw = _b64url_decode(spec)
        except (ValueError, TypeError):
            raw = b""
        if alg == "EdDSA" and len(raw) == 32:
            return Ed25519PublicKey.from_public_bytes(raw)
        return serialization.load_pem_public_key(spec.encode("utf-8"))
    if isinstance(spec, bytes):
        if alg == "EdDSA" and len(spec) == 32:
            return Ed25519PublicKey.from_public_bytes(spec)
        return serialization.load_pem_public_key(spec)
    raise ValueError("unsupported key spec")


def _verify_signature(public: Any, alg: str, signing_input: bytes, signature: bytes) -> bool:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

    try:
        if alg == "EdDSA" and isinstance(public, ed25519.Ed25519PublicKey):
            public.verify(signature, signing_input)
        elif alg == "ES256" and isinstance(public, ec.EllipticCurvePublicKey):
            public.verify(signature, signing_input, ec.ECDSA(hashes.SHA256()))
        elif alg == "RS256" and isinstance(public, rsa.RSAPublicKey):
            public.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        else:
            return False
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _provenance(
    card: Mapping[str, Any], outcome: str, reason: str, **extra: Any
) -> CardProvenance:
    agent, org = _card_identity(card)
    return CardProvenance(
        outcome=outcome,
        reason=reason,
        card_digest=card_digest(card),
        agent=agent,
        org=org,
        **extra,
    )


def verify_agent_card(
    card: Mapping[str, Any],
    *,
    keys: Mapping[str, Any] | None = None,
    keys_path: str | None = None,
) -> CardProvenance:
    """Deterministically verify a signed agent card; never raises on a bad card.

    Returns a :class:`CardProvenance` whose ``outcome`` is ``verified`` only when
    a held key validates the JWS over the canonical card. Everything else is
    ``unverified`` with an explicit ``reason``.
    """
    signatures = card.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return _provenance(card, OUTCOME_UNVERIFIED, "unsigned")
    signature = next((item for item in signatures if isinstance(item, Mapping)), None)
    if signature is None:
        return _provenance(card, OUTCOME_UNVERIFIED, "malformed-signature")
    protected = signature.get("protected")
    raw_signature = signature.get("signature")
    if not isinstance(protected, str) or not isinstance(raw_signature, str):
        return _provenance(card, OUTCOME_UNVERIFIED, "malformed-signature")
    try:
        header = json.loads(_b64url_decode(protected))
    except (ValueError, TypeError):
        return _provenance(card, OUTCOME_UNVERIFIED, "malformed-signature")
    alg = header.get("alg") if isinstance(header, Mapping) else None
    kid = header.get("kid") if isinstance(header, Mapping) else None
    if not isinstance(alg, str) or alg not in _SUPPORTED_ALGS:
        return _provenance(
            card, OUTCOME_UNVERIFIED, "unsupported-alg", alg=alg if isinstance(alg, str) else None
        )

    payload = base64.urlsafe_b64encode(canonical_bytes(card)).rstrip(b"=").decode("ascii")
    signing_input = f"{protected}.{payload}".encode("ascii")
    signature_bytes = _b64url_decode(raw_signature)

    resolved = _load_keys(keys, keys_path)
    spec = resolved.get(kid) if isinstance(kid, str) else None
    if spec is None:
        return _provenance(card, OUTCOME_UNVERIFIED, "key-unavailable", key_id=kid, alg=alg)
    try:
        public = _public_key(spec, alg)
    except (ValueError, TypeError):
        return _provenance(card, OUTCOME_UNVERIFIED, "key-invalid", key_id=kid, alg=alg)
    if _verify_signature(public, alg, signing_input, signature_bytes):
        return _provenance(card, OUTCOME_VERIFIED, "signature-valid", key_id=kid, alg=alg)
    return _provenance(card, OUTCOME_UNVERIFIED, "signature-invalid", key_id=kid, alg=alg)


__all__ = [
    "KEYS_ENV",
    "OUTCOME_UNVERIFIED",
    "OUTCOME_VERIFIED",
    "CardProvenance",
    "canonical_bytes",
    "card_digest",
    "key_id",
    "verify_agent_card",
]