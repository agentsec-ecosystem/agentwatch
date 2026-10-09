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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

EXPERIMENTAL = True
KEY_FILENAME = "signing.key"
KEY_ROTATION_TOOL = "key-rotation"


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
            "signing requires the optional 'cryptography' dependency; "
            "install agentsec-agentwatch[signing]"
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
        # Raw key bytes must NOT be stripped: whitespace bytes are valid key
        # material, and stripping truncates the key (a corrupt-key bug).
        data = path.read_bytes()
        if data:
            if len(data) != 32:
                raise SigningError(
                    f"signing key {path} is malformed ({len(data)} bytes; expected 32)"
                )
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


@dataclass(frozen=True)
class RotationResult:
    """The outcome of rotating the installation key: the old id and the new key."""

    previous_key_id: str | None
    key: SigningKey


def rotate_key(path: Path) -> RotationResult:
    """Replace the installation key at ``path`` with a fresh one.

    The old key is not retained (losing it only ends an epoch); what matters is
    that the *rotation itself* is recorded as a chain event, so a verifier can
    tie a signature to the epoch key it belongs to.
    """
    from agentwatch import posture

    previous = load_or_create_key(path).key_id if path.exists() else None
    posture.secure_dir(path.parent)
    new_key = generate_key()
    path.write_bytes(new_key.private_bytes)
    posture.secure_file(path)
    return RotationResult(previous_key_id=previous, key=new_key)


@dataclass(frozen=True)
class KeyRotation:
    """One recorded key rotation (a metadata-only chain event)."""

    previous_key_id: str | None
    new_key_id: str
    at: datetime
    seq: int = 0


def key_rotation_record(
    previous_key_id: str | None,
    new_key_id: str,
    *,
    at: datetime | None = None,
) -> AgentRecord:
    """Build the metadata-only marker record for a key rotation."""
    return AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=KEY_ROTATION_TOOL,
            arguments={"previous_key_id": previous_key_id, "new_key_id": new_key_id},
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=at or datetime.now(timezone.utc),
        producer=MARKER_PRODUCER,
    )


def record_key_rotation(
    store: RecordStore,
    previous_key_id: str | None,
    new_key_id: str,
    *,
    now: datetime | None = None,
) -> int:
    """Append a ``key-rotation`` chain event; return its sequence number."""
    entry = store.append(key_rotation_record(previous_key_id, new_key_id, at=now))
    return entry.seq


def key_rotations(store: RecordStore) -> list[KeyRotation]:
    """Every recorded key rotation, in chain order."""
    rotations: list[KeyRotation] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != KEY_ROTATION_TOOL:
            continue
        arguments = record.tool.arguments or {}
        new_key_id = arguments.get("new_key_id")
        if new_key_id is None:
            continue
        previous = arguments.get("previous_key_id")
        rotations.append(
            KeyRotation(
                previous_key_id=str(previous) if previous is not None else None,
                new_key_id=str(new_key_id),
                at=record.started_at,
                seq=entry.seq,
            )
        )
    return rotations


@dataclass(frozen=True)
class SigningStatus:
    """The installation's signing posture, honest about a key we do not hold."""

    key_id: str | None
    key_present: bool
    epoch: int = 0

    @property
    def summary(self) -> str:
        if self.key_id is None:
            return "not configured (optional; `checkpoint export --sign`)"
        if self.key_present:
            return f"signed by key {self.key_id} (epoch {self.epoch})"
        return f"signed by key id {self.key_id}, key unavailable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_present": self.key_present,
            "epoch": self.epoch,
            "summary": self.summary,
        }


def signing_status(store: RecordStore | None, store_dir: Path) -> SigningStatus:
    """Derive the signing posture from the recorded epochs and the held key.

    The epoch id comes from the latest recorded rotation; the key file only
    tells us whether we can still *verify* that epoch. A recorded epoch whose
    key is gone reports "key unavailable" instead of passing silently.
    """
    rotations = key_rotations(store) if store is not None else []
    key_id = rotations[-1].new_key_id if rotations else None
    epoch = len(rotations) + 1 if rotations else 0

    held: SigningKey | None = None
    path = store_dir / KEY_FILENAME
    if path.exists():
        try:
            held = load_or_create_key(path)
        except SigningError:
            held = None
    if key_id is None and held is not None:
        key_id = held.key_id
        epoch = 1
    key_present = held is not None and (key_id is None or held.key_id == key_id)
    return SigningStatus(key_id=key_id, key_present=key_present, epoch=epoch)


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
        data = path.read_bytes()
        if len(data) != 32:
            return False
        return key_from_private(data).key_id == key_id
    except (OSError, SigningError, ValueError):  # pragma: no cover - unreadable key
        return False


__all__ = [
    "EXPERIMENTAL",
    "KEY_FILENAME",
    "KEY_ROTATION_TOOL",
    "KeyRotation",
    "RotationResult",
    "SigningError",
    "SigningKey",
    "SigningStatus",
    "generate_key",
    "key_available",
    "key_from_private",
    "key_id_for",
    "key_rotation_record",
    "key_rotations",
    "load_or_create_key",
    "record_key_rotation",
    "rotate_key",
    "sign_digest",
    "signing_key_id",
    "signing_status",
    "verify_digest",
]
