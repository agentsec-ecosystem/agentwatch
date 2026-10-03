"""Published plumbing contract (M10 J1, #203).

The versioned, published specs the ecosystem and community adapters build on:
the store envelope, the daemon socket frame, and the adapter conformance
contract. The reference docs (`docs/reference/store-format.md`,
`docs/reference/daemon-protocol.md`, `docs/reference/adapter-api.md`) describe
these values; the runtime and `tests/test_protocol_contract.py` pin them so the
docs cannot silently drift.

Compatibility: additive minor, breaking major + deprecation.
"""

from __future__ import annotations

PROTOCOL_VERSION = "0.1.0"

# -- store format -----------------------------------------------------------

STORE_FORMAT_VERSION = 1
STORE_FORMAT_MARKER_KEY = "format"
STORE_ENVELOPE_KEYS = ("seq", "prev_hash", "hash", "record")
TOMBSTONE_KEYS = ("seq", "prev_hash", "hash", "tombstone", "purged_at")
GENESIS_PREV_HASH = "0" * 64

# -- daemon socket protocol -------------------------------------------------

FRAME_PHASES = (
    "pre",
    "post",
    "denied",
    "prompt",
    "session-start",
    "session-end",
    "hook-error",
    "event",
)
FRAME_KEYS = ("phase", "harness", "event")
