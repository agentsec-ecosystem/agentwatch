"""Session-start recorder attestation (M29 DEP-2, #442; PRD 50).

The hash chain proves stored records were not altered; it cannot prove recording
was **on**. Stripping the hook config leaves no chain record, so a store that
verifies clean can be *empty* rather than *complete*.

This module appends a session-start attestation fact — which hook sources were
effective, a **keyed digest** of the effective hook/permission config, whether
managed-only policy applied, the permission mode, and the recorder version — and
a ``recorder-config-changed`` observation when that digest changes. Only digests
and booleans are stored; **never** config values or secrets.

Non-claims: the attestation states that recording was configured to run, not
that no attacker modified the store (same-user forgery is out of scope) and not
that every call was captured (that is ``coverage``). The digest is keyed like
content-flow fingerprints, so it cannot be confirmed from a leaked store without
the key.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentwatch import flow
from agentwatch.recorder_state import (
    RECORDER_ATTESTED_TOOL,
    MarkerReport,
    record_attestation,
    record_recorder_config_changed,
    recorder_markers,
)
from agentwatch.store import RecordStore

ATTESTATION_PRESENT = "present"
ATTESTATION_ABSENT = "absent"
PERMISSION_MODE_UNKNOWN = "unknown"

# The effective hook sources, always recorded as booleans.
HOOK_SOURCES: tuple[str, ...] = ("managed", "user", "project", "plugin")


@dataclass(frozen=True)
class Attestation:
    """A stored attestation fact (read side)."""

    hook_sources: dict[str, bool]
    config_digest: str
    managed_policy: bool
    permission_mode: str
    recorder_version: str
    attestation: str = ATTESTATION_PRESENT
    seq: int | None = None


@dataclass(frozen=True)
class AttestationReport:
    """Outcome of appending one session-start attestation."""

    marker: MarkerReport
    config_changed: MarkerReport | None = None


def default_recorder_version() -> str:
    """The agentwatch package version, or a stable placeholder in a source checkout."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always present on 3.10+
        return "0.0.0"
    try:
        return version("agentsec-agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.0.0+source"


def config_digest(
    *,
    hook_sources: Mapping[str, bool],
    managed_policy: bool,
    permission_mode: str,
    key: bytes | None = None,
) -> str:
    """A stable keyed digest of the effective hook/permission config (booleans only).

    The canonical payload contains only booleans, the permission-mode name, and
    the source names — never a config value. Keyed with the per-install HMAC key
    when available (see ``flow``); an unkeyed SHA-256 prefix is the fallback so a
    digest always exists in a keyless context.
    """
    canonical = json.dumps(
        {
            "hook_sources": {name: bool(hook_sources.get(name, False)) for name in HOOK_SOURCES},
            "managed_policy": bool(managed_policy),
            "permission_mode": str(permission_mode),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    resolved = key if key is not None else flow.hmac_key_or_none()
    if resolved:
        return flow.fingerprint(canonical, key=resolved)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _sources(
    *, managed: bool, user: bool, project: bool, plugin: bool
) -> dict[str, bool]:
    return {
        "managed": bool(managed),
        "user": bool(user),
        "project": bool(project),
        "plugin": bool(plugin),
    }


def attest_session(
    store: RecordStore,
    *,
    managed: bool = False,
    user: bool = False,
    project: bool = False,
    plugin: bool = False,
    managed_policy: bool = False,
    permission_mode: str = PERMISSION_MODE_UNKNOWN,
    recorder_version: str | None = None,
    key: bytes | None = None,
    now: datetime | None = None,
) -> AttestationReport:
    """Append a session-start attestation, plus ``recorder-config-changed`` on a digest move.

    The attestation is coalesced when identical to the last one (so repeated
    starts on an unchanged config do not spam the chain); a changed digest always
    produces a ``recorder-config-changed`` observation **before** the new fact.
    """
    sources = _sources(managed=managed, user=user, project=project, plugin=plugin)
    version = recorder_version or default_recorder_version()
    digest = config_digest(
        hook_sources=sources,
        managed_policy=managed_policy,
        permission_mode=permission_mode,
        key=key,
    )
    previous = last_attestation(store)

    config_changed: MarkerReport | None = None
    if previous is not None and previous.config_digest != digest:
        changed: dict[str, bool] = {}
        for name in HOOK_SOURCES:
            if previous.hook_sources.get(name, False) != sources[name]:
                changed[name] = True
        if previous.managed_policy != bool(managed_policy):
            changed["managed_policy"] = True
        if previous.permission_mode != permission_mode:
            changed["permission_mode"] = True
        config_changed = record_recorder_config_changed(
            store,
            old_digest=previous.config_digest,
            new_digest=digest,
            changed=changed,
            now=now,
        )

    marker = record_attestation(
        store,
        {
            "attestation": ATTESTATION_PRESENT,
            "config_digest": digest,
            "hook_sources": sources,
            "managed_policy": bool(managed_policy),
            "permission_mode": str(permission_mode),
            "recorder_version": version,
        },
        now=now,
    )
    return AttestationReport(marker=marker, config_changed=config_changed)


def _attestation_from(marker: Any) -> Attestation:
    arguments = marker.arguments
    raw_sources = arguments.get("hook_sources")
    sources = raw_sources if isinstance(raw_sources, Mapping) else {}
    return Attestation(
        hook_sources={name: bool(sources.get(name, False)) for name in HOOK_SOURCES},
        config_digest=str(arguments.get("config_digest", "")),
        managed_policy=bool(arguments.get("managed_policy", False)),
        permission_mode=str(arguments.get("permission_mode", PERMISSION_MODE_UNKNOWN)),
        recorder_version=str(arguments.get("recorder_version", "")),
        attestation=str(arguments.get("attestation", ATTESTATION_PRESENT)),
        seq=marker.seq,
    )


def last_attestation(store: RecordStore) -> Attestation | None:
    """The newest stored attestation, or ``None`` when none was ever recorded."""
    for marker in reversed(recorder_markers(store)):
        if marker.tool == RECORDER_ATTESTED_TOOL:
            return _attestation_from(marker)
    return None


def attestation_status(store: RecordStore) -> str:
    """``present`` when any attestation is stored, else ``absent``."""
    return ATTESTATION_PRESENT if last_attestation(store) is not None else ATTESTATION_ABSENT


__all__ = [
    "ATTESTATION_ABSENT",
    "ATTESTATION_PRESENT",
    "HOOK_SOURCES",
    "PERMISSION_MODE_UNKNOWN",
    "Attestation",
    "AttestationReport",
    "attest_session",
    "attestation_status",
    "config_digest",
    "default_recorder_version",
    "last_attestation",
]
