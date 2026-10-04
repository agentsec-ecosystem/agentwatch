"""Store-access audit records (M15 S21, #235).

Every control in the store is about *writing* integrity; nothing says who read the
store and moved its data into a portable artifact. This module appends a
metadata-only ``store-access`` record for the operations that move data off-machine
or into a bundle — an explicit allow-list (``export``, ``export-session``,
``evidence``, ``bom``). Local read-only ``search``/``view``/``replay`` are out of
scope by decision, so the chain does not fill with read noise.

The record never carries credentials or record payloads: a command, a scope
(session ids + record count), a destination *kind*, and — for a failed attempt —
the error. It records an action already taken; it never gates one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

STORE_ACCESS_TOOL = "store-access"

# The allow-list boundary: "data left, or could leave".
ACCESS_COMMANDS: tuple[str, ...] = (
    "export",
    "export-session",
    "evidence",
    "bom",
    "quarantine-inspect",
)


class DestinationKind(str, Enum):
    """Where the data went; never a path or credential."""

    FILE = "file"
    STDOUT = "stdout"
    BUNDLE = "bundle"
    OTLP = "otlp"


@dataclass(frozen=True)
class StoreAccessReport:
    """Outcome of appending one store-access record."""

    seq: int
    command: str
    attempted: bool


def record_store_access(
    store: RecordStore,
    *,
    command: str,
    sessions: list[str] | tuple[str, ...] = (),
    records: int = 0,
    destination_kind: DestinationKind | str = DestinationKind.STDOUT,
    attempted: bool = False,
    error: str | None = None,
    now: datetime | None = None,
) -> StoreAccessReport:
    """Append exactly one metadata-only ``store-access`` record.

    ``attempted`` marks a failed operation (the error is carried); the access was
    still an access and is never silently dropped.
    """
    if command not in ACCESS_COMMANDS:
        raise ValueError(f"{command!r} is not an audited access command")
    kind = (
        destination_kind.value
        if isinstance(destination_kind, DestinationKind)
        else str(destination_kind)
    )
    arguments: dict[str, Any] = {
        "command": command,
        "scope": {"sessions": list(sessions), "records": records},
        "destination_kind": kind,
    }
    if attempted:
        arguments["attempted"] = True
        if error:
            arguments["error"] = error
    record = AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=STORE_ACCESS_TOOL,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.ERROR if attempted else Outcome.OK,
        started_at=now or datetime.now(timezone.utc),
        producer=MARKER_PRODUCER,
    )
    entry = store.append(record)
    return StoreAccessReport(seq=entry.seq, command=command, attempted=attempted)


@dataclass(frozen=True)
class StoreAccess:
    """One stored access record, for read-side reporting."""

    command: str
    sessions: tuple[str, ...]
    records: int
    destination_kind: str
    attempted: bool
    error: str | None
    at: datetime
    seq: int = field(default=0)


def store_accesses(store: RecordStore) -> list[StoreAccess]:
    """Every stored access record, in store order."""
    result: list[StoreAccess] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != STORE_ACCESS_TOOL:
            continue
        arguments = record.tool.arguments or {}
        scope = arguments.get("scope")
        scope = scope if isinstance(scope, dict) else {}
        sessions = scope.get("sessions")
        result.append(
            StoreAccess(
                command=str(arguments.get("command", "")),
                sessions=tuple(str(s) for s in sessions) if isinstance(sessions, list) else (),
                records=int(scope.get("records", 0) or 0),
                destination_kind=str(arguments.get("destination_kind", "")),
                attempted=bool(arguments.get("attempted", False)),
                error=str(arguments["error"]) if "error" in arguments else None,
                at=record.started_at,
                seq=entry.seq,
            )
        )
    return result
