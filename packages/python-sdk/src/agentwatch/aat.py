"""IETF Agent Audit Trail export mapping (M25 AAT-1/AAT-2, PRD 41).

Emits agentwatch records in the IETF Agent Audit Trail (AAT) shape plus the
store chain envelope, so a third-party AAT consumer can read the records *and*
independently verify the chain segment. This is an export/ingest format over the
source-of-truth record schema (ADR-0016) — never a replacement for it.

Two honesty rules:

* **lossless-or-explicit** — fields we cannot populate are listed in ``unmapped``
  with a reason; a value is never invented.
* **cite the revision** — we claim conformance to a pinned draft revision, never
  to a stable standard, and the revision rides in every bundle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.records import (
    AgentRecord,
    StepType,
    effective_producer,
    effective_record_phase,
)

AAT_DRAFT = "draft-sharif-agent-audit-trail-06"
AAT_EXPORT_SCHEMA = "agentwatch-aat-export/1"

# AAT concept -> agentwatch source. Published in docs/design/aat-mapping.md.
AAT_MAPPING: dict[str, str] = {
    "agent": "agent_identity (IDN-1)",
    "action_type": "step_type taxonomy (act/observe/reason/verify)",
    "outcome": "record outcome (ok/error/denied)",
    "record_phase": "record_phase (AAT-1), never inferred",
    "trust_level": "derived from producer kind + chain linkage; not a verdict",
    "chain": "store envelope seq/prev_hash/hash",
    "timestamp": "started_at / ended_at (UTC)",
}

# AAT fields agentwatch cannot yet populate: surfaced, never invented.
_UNMAPPED_FIELDS: dict[str, str] = {
    "response_hash": "no pre-redaction response fingerprint captured on the record",
    "response_size": "pre-redaction response byte size not captured on the record",
}

_ACTION_TYPES = {
    StepType.REASON: "reason",
    StepType.ACT: "act",
    StepType.OBSERVE: "observe",
    StepType.VERIFY: "verify",
}


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def aat_entry_hash(prev_hash: str, record: dict[str, Any]) -> str:
    """The chain hash for one AAT entry: ``sha256(prev_hash + canonical(record))``."""
    return hashlib.sha256((prev_hash + _canonical(record)).encode("utf-8")).hexdigest()


def aat_entry_chain_error(entry: Any, prev_hash: str | None) -> str | None:
    """Why an AAT entry's chain is untrusted, or ``None`` when it verifies.

    Checks the entry's own hash over its embedded native record *and* its
    declared ``prev_hash`` against the preceding entry's declared hash. Never
    raises (untrusted input); the caller quarantines on a reason.
    """
    if not isinstance(entry, dict):
        return "entry is not an object"
    native = entry.get("agentwatch")
    chain = entry.get("chain")
    if not isinstance(native, dict) or not isinstance(chain, dict):
        return "missing agentwatch record or chain envelope"
    declared_prev = chain.get("prev_hash")
    declared_hash = chain.get("hash")
    if not isinstance(declared_prev, str) or not isinstance(declared_hash, str):
        return "chain envelope has no prev_hash/hash"
    if prev_hash is not None and declared_prev != prev_hash:
        return "chain linkage broken: prev_hash does not match the preceding entry"
    if aat_entry_hash(declared_prev, native) != declared_hash:
        return "chain hash does not match the record (tampered)"
    return None


def _iso(value: Any) -> str | None:
    return value.astimezone().isoformat() if hasattr(value, "isoformat") else None


def _identity_block(record: AgentRecord) -> dict[str, Any]:
    """The AAT agent-identity block (IDN-1), omitting absent facts."""
    agent = record.agent
    block: dict[str, Any] = {"name": agent.name or agent.identity}
    if agent.version:
        block["version"] = agent.version
    if record.harness:
        block["harness"] = record.harness
    if agent.model_version:
        block["model"] = agent.model_version
    if agent.workload_identity:
        block["workload_identity"] = agent.workload_identity
    if agent.credential_class is not None:
        block["credential_class"] = agent.credential_class.value
    if agent.principal:
        block["principal"] = agent.principal
    if agent.delegation_chain:
        block["delegation_chain"] = list(agent.delegation_chain)
    return block


def _action_type(record: AgentRecord) -> str:
    if record.step_type is not None:
        return _ACTION_TYPES[record.step_type]
    return "tool_call"


def _trust_level(record: AgentRecord) -> dict[str, Any]:
    return {"source": effective_producer(record).kind.value, "chain": "linked"}


def aat_record(record: AgentRecord, *, seq: int, prev_hash: str, hash: str) -> dict[str, Any]:
    """One record in AAT shape; agentwatch-native record preserved for losslessness."""
    return {
        "aat_version": AAT_DRAFT,
        "agent": _identity_block(record),
        "action_type": _action_type(record),
        "outcome": record.outcome.value,
        "record_phase": effective_record_phase(record).value,
        "trust_level": _trust_level(record),
        "timestamp": _iso(record.started_at),
        "chain": {"seq": seq, "prev_hash": prev_hash, "hash": hash},
        # Native source of truth: keeps the export lossless and lets a consumer
        # recompute the chain hash over the exact canonical record.
        "agentwatch": record.to_dict(),
        "unmapped": dict(_UNMAPPED_FIELDS),
    }


def export_aat(export: Any, *, privacy_mode: str) -> dict[str, Any]:
    """Build the AAT bundle for a session export (records + chain + coverage block)."""
    entries: list[dict[str, Any]] = []
    for row in export.rows:
        record = AgentRecord.from_dict(row["record"])
        entries.append(
            aat_record(
                record,
                seq=int(row["seq"]),
                prev_hash=str(row["prev_hash"]),
                hash=str(row["hash"]),
            )
        )
    return {
        "schema": AAT_EXPORT_SCHEMA,
        "aat_version": AAT_DRAFT,
        "session_id": export.session_id,
        "privacy_mode": privacy_mode,
        "records": entries,
        "coverage": {
            "records": len(entries),
            "chain": "included",
            "privacy_mode": privacy_mode,
            "unmapped_fields": sorted(_UNMAPPED_FIELDS),
        },
    }


def to_aat_json(bundle: dict[str, Any]) -> str:
    """Render a bundle as deterministic, pretty JSON (stable ordering)."""
    return json.dumps(bundle, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_aat(bundle: dict[str, Any], path: Path) -> None:
    """Write an AAT bundle to ``path`` atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(to_aat_json(bundle), encoding="utf-8")
    tmp.replace(path)


def verify_aat(bundle: Any) -> bool:
    """Reference consumer: re-verify each entry's hash and inter-entry linkage.

    Fails closed on any malformed shape (never raises on untrusted input).
    """
    return verify_aat_report(bundle).ok


@dataclass(frozen=True)
class AATProblem:
    """One entry that failed verification (index ``-1`` = bundle-level)."""

    index: int
    reason: str


@dataclass(frozen=True)
class AATVerification:
    """The full verdict for a bundle (gap-free, per-entry)."""

    ok: bool
    problems: tuple[AATProblem, ...] = ()


def verify_aat_report(bundle: Any) -> AATVerification:
    """Verify a bundle and report *which* entries failed, with reasons.

    Bundle-level failures (not an object, wrong revision, no records) report a
    single problem at index ``-1``. Per-entry failures report the entry index;
    a failing entry never cascades into false linkage errors for its successors.
    """
    if not isinstance(bundle, dict):
        return AATVerification(False, (AATProblem(-1, "bundle is not a JSON object"),))
    if bundle.get("aat_version") != AAT_DRAFT:
        return AATVerification(False, (AATProblem(-1, "unsupported AAT revision"),))
    entries = bundle.get("records")
    if not isinstance(entries, list):
        return AATVerification(False, (AATProblem(-1, "bundle has no records list"),))
    problems: list[AATProblem] = []
    prev_hash: str | None = None
    for index, entry in enumerate(entries):
        reason = aat_entry_chain_error(entry, prev_hash)
        if reason is not None:
            problems.append(AATProblem(index, reason))
        chain = entry.get("chain") if isinstance(entry, dict) else None
        declared = chain.get("hash") if isinstance(chain, dict) else None
        if isinstance(declared, str):
            prev_hash = declared
    return AATVerification(not problems, tuple(problems))


__all__ = [
    "AAT_DRAFT",
    "AAT_EXPORT_SCHEMA",
    "AAT_MAPPING",
    "AATProblem",
    "AATVerification",
    "aat_entry_chain_error",
    "aat_entry_hash",
    "aat_record",
    "export_aat",
    "to_aat_json",
    "verify_aat",
    "verify_aat_report",
    "write_aat",
]