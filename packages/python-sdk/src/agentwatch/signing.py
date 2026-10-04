"""Optional signed checkpoints (M22 W9, PRD 39).

Hash chains give integrity, not origin. A local ed25519 signature over a
checkpoint digest adds non-repudiation — "this checkpoint was produced by this
installation" — turning a bundle from *internally consistent* into *attributable*.
It is explicitly **not** "attributable to this human."

The signing key only ever signs digests, so there is no recovery problem: lose
it and you start a new key epoch; nothing becomes unreadable. Signing is opt-in
and requires the optional ``cryptography`` dependency (the ``agentsec-agentwatch[signing]``
extra), so the core SDK stays dependency-light (NFR-5).
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPERIMENTAL = True
KEY_FILENAME = "signing.key"


class SigningError(RuntimeError):
    """Raised when signing is requested without the optional dependency."""


@dataclass(frozen=True)
class SigningKey:
    """One installation's ed25519 signing key and its derived key id."""

    key_id: str
    private_bytes: bytes
    public_bytes: bytes


def _ed25519() -> tuple[Any, Any, Any]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise SigningError(
            "signing requires the optional 'cryptography' dependency; install agentsec-agentwatch[signing]"
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey, serialization


def key_id_for(public_bytes: bytes) -> str:
    """A stable short id for a public key (metadata, not a secret)."""
    return hashlib.sha256(public_bytes).hexdigest()[:16]


def generate_key() -> SigningKey:
    """Generate a new ed25519 key for this installation."""
    private_cls, _public_cls, serialization = _ed25519()
    private = private_cls.generate()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return SigningKey(
        key_id=key_id_for(public_bytes), private_bytes=private_bytes, public_bytes=public_bytes
    )


def key_from_private(private_bytes: bytes) -> SigningKey:
    """Derive the public key and id from raw private bytes."""
    private_cls, _public_cls, serialization = _ed25519()
    private = private_cls.from_private_bytes(private_bytes)
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return SigningKey(
        key_id=key_id_for(public_bytes), private_bytes=private_bytes, public_bytes=public_bytes
    )


def load_or_create_key(path: Path) -> SigningKey:
    """Load the installation key at ``path`` (0600) or create it."""
    from agentwatch import posture

    if path.exists():
        data = path.read_bytes().strip()
        if data:
            return key_from_private(data)
    posture.secure_dir(path.parent)
    data = os.urandom(32)
    key = key_from_private(data)
    path.write_bytes(key.private_bytes)
    posture.secure_file(path)
    return key


def signing_key_id(key: SigningKey | None) -> str | None:
    """The key id, or ``None`` when no key is configured."""
    return key.key_id if key is not None else None


def sign_digest(key: SigningKey, digest_hex: str) -> str:
    """Sign a checkpoint digest with this installation's key (base64 signature)."""
    private_cls, _public_cls, _serialization = _ed25519()
    private = private_cls.from_private_bytes(key.private_bytes)
    signature = private.sign(digest_hex.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def verify_digest(public_bytes: bytes, digest_hex: str, signature_b64: str) -> bool:
    """Verify a signature over ``digest_hex``; a bad signature returns False."""
    from cryptography.exceptions import InvalidSignature

    _private_cls, public_cls, _serialization = _ed25519()
    try:
        public = public_cls.from_public_bytes(public_bytes)
        signature = base64.b64decode(signature_b64)
        public.verify(signature, digest_hex.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def key_available(key_id: str, *, key_dir: Path | None = None) -> bool:
    """Whether we hold a public key for ``key_id`` (else report unavailable)."""
    if key_dir is None:
        return False
    path = key_dir / KEY_FILENAME
    if not path.exists():
        return False
    try:
        return key_from_private(path.read_bytes().strip()).key_id == key_id
    except (OSError, SigningError):  # pragma: no cover - unreadable key
        return False


__all__ = [
    "EXPERIMENTAL",
    "KEY_FILENAME",
    "SigningError",
    "SigningKey",
    "generate_key",
    "key_available",
    "key_from_private",
    "key_id_for",
    "load_or_create_key",
    "sign_digest",
    "signing_key_id",
    "verify_digest",
]
