"""Optional checkpoint notarization (M22 W7, PRD 39).

PRD 14 rejects blockchain anchoring as theater; the real need — *prove the chain
existed in this state at time T* — has a boring standard answer: **RFC 3161**
timestamping, or publishing the checkpoint digest somewhere append-only the
operator already trusts (commit it to git, email it to yourself).

`agentwatch checkpoint export` emits the latest checkpoint's digest; with an
operator-configured TSA (off by default, explicit opt-in — the same gate as OTLP
export) it attaches an RFC 3161 token. A TSA that is unreachable never loses the
digest: the export succeeds and states ``digest-only``.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentwatch.signing import SigningKey, sign_digest, signing_key_id
from agentwatch.store import RecordStore

CHECKPOINT_FORMAT = "agentwatch-checkpoint/1"
TIMESTAMP_TIMEOUT_SECONDS = 5.0

# DER-encoded OIDs / constants for the RFC 3161 TimeStampReq.
_SHA256_OID = bytes.fromhex("0609608648016503040201")
_NULL = b"\x05\x00"


def _der_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _der(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _der_length(len(content)) + content


def _der_integer(value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return _der(0x02, raw)


def build_timestamp_request(digest_hex: str) -> bytes:
    """A minimal RFC 3161 ``TimeStampReq`` (DER) over a checkpoint digest.

    ``messageImprint.hashedMessage`` is ``sha256`` of the checkpoint digest — the
    digest is itself hashed so the TSA never sees a value that could be replayed
    as the message.
    """
    imprint = hashlib.sha256(bytes.fromhex(digest_hex)).digest()
    algorithm = _der(0x30, _SHA256_OID + _NULL)
    message = _der(0x30, algorithm + _der(0x04, imprint))
    return _der(0x30, _der_integer(1) + message)


@dataclass(frozen=True)
class TimestampResult:
    """An RFC 3161 token, or the reason it is absent (never a hard failure)."""

    token: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.token is not None


def _default_poster(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return bytes(response.read())


def request_timestamp(
    digest_hex: str,
    tsa_url: str,
    *,
    poster: Callable[[urllib.request.Request, float], bytes] | None = None,
    timeout: float = TIMESTAMP_TIMEOUT_SECONDS,
) -> TimestampResult:
    """Request an RFC 3161 token; return ``ok=False`` with a note on any failure."""
    request = urllib.request.Request(  # noqa: S310
        tsa_url,
        data=build_timestamp_request(digest_hex),
        headers={"Content-Type": "application/timestamp-query"},
        method="POST",
    )
    send = poster or _default_poster
    try:
        raw = send(request, timeout)
    except (OSError, ValueError) as exc:
        return TimestampResult(error=f"TSA unreachable: {exc}")
    import base64

    return TimestampResult(token=base64.b64encode(raw).decode("ascii"))


@dataclass(frozen=True)
class CheckpointExport:
    """One exported checkpoint: digest, optional signature, optional TSA token."""

    format: str
    seq: int
    entries: int
    at: datetime
    digest: str
    key_id: str | None = None
    signature: str | None = None
    timestamp_token: str | None = None
    note: str | None = None

    @property
    def signed(self) -> bool:
        return self.signature is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "seq": self.seq,
            "entries": self.entries,
            "at": self.at.isoformat(),
            "digest": self.digest,
            "key_id": self.key_id,
            "signature": self.signature,
            "timestamp_token": self.timestamp_token,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointExport:
        from datetime import datetime as _datetime

        return cls(
            format=str(data.get("format", CHECKPOINT_FORMAT)),
            seq=int(data.get("seq", 0)),
            entries=int(data.get("entries", 0)),
            at=_datetime.fromisoformat(str(data.get("at"))),
            digest=str(data["digest"]),
            key_id=data.get("key_id"),
            signature=data.get("signature"),
            timestamp_token=data.get("timestamp_token"),
            note=data.get("note"),
        )


def export_checkpoint(
    store: RecordStore,
    *,
    signer: SigningKey | None = None,
    timestamp: Callable[[str], TimestampResult] | None = None,
) -> CheckpointExport:
    """Export the latest checkpoint (or the chain head) as an attributable digest."""
    entry = _latest_entry(store)
    digest = entry.hash
    signature = sign_digest(signer, digest) if signer is not None else None
    token: str | None = None
    note: str | None = None
    if timestamp is not None:
        result = timestamp(digest)
        token = result.token
        if not result.ok:
            note = result.error or "timestamp unavailable; digest-only"
    if token is None and note is None:
        note = "digest-only"
    at = datetime.now().astimezone()
    return CheckpointExport(
        format=CHECKPOINT_FORMAT,
        seq=entry.seq,
        entries=entry.entries if entry.entries is not None else 0,
        at=at,
        digest=digest,
        key_id=signing_key_id(signer) if signer is not None else None,
        signature=signature,
        timestamp_token=token,
        note=note,
    )


def _latest_entry(store: RecordStore) -> Any:
    entries = store.entries()
    if not entries:
        raise ValueError("store is empty; nothing to notarize")
    checkpoints = [entry for entry in entries if entry.checkpoint]
    return checkpoints[-1] if checkpoints else entries[-1]


def render_checkpoint(export: CheckpointExport) -> str:
    lines = [f"agentwatch checkpoint export ({export.format})"]
    lines.append(f"  seq: {export.seq}  entries: {export.entries}")
    lines.append(f"  digest: {export.digest}")
    if export.key_id:
        lines.append(f"  signed by key {export.key_id}")
    if export.timestamp_token:
        lines.append("  timestamp: RFC 3161 token attached")
    if export.note:
        lines.append(f"  note: {export.note}")
    return "\n".join(lines)


def verify_checkpoint(export: CheckpointExport, public_key: bytes) -> bool:
    """Verify a checkpoint's signature against a public key, or raise if unsigned."""
    from agentwatch.signing import verify_digest

    if export.signature is None:
        raise ValueError("checkpoint is not signed")
    return verify_digest(public_key, export.digest, export.signature)


def dumps(export: CheckpointExport) -> str:
    return json.dumps(export.to_dict(), sort_keys=True, ensure_ascii=False) + "\n"


__all__ = [
    "CHECKPOINT_FORMAT",
    "CheckpointExport",
    "TimestampResult",
    "build_timestamp_request",
    "dumps",
    "export_checkpoint",
    "render_checkpoint",
    "request_timestamp",
    "verify_checkpoint",
]
