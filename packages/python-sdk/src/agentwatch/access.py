"""Fleet role x data-class read-access model + self-visible access log (M29 ACC-1, #448).

PRD 56 §ACC-1, design [access-and-governance](../../../../docs/design/access-and-governance.md).
Recording individuals' agent activity is an employee-monitoring surface; a
fleet/console multi-user view must say **who may read whose sessions, at what
fidelity**, and must record every cross-user read so the subject can see it.

The model is a documented, enforceable ``role x data-class`` matrix:

* roles — ``self`` / ``team-reviewer`` / ``security-auditor`` / ``admin``;
* data classes — ``metadata`` / ``identity-hashed`` / ``identity-resolved`` /
  ``content`` / ``evidence``.

Rules (least-privileged default):

* a cross-user read the role is not granted returns **nothing** and is itself
  appended as a ``store-access`` record (S21);
* the owner reading their own record is not a cross-user read and is not logged
  as one;
* ``identity-resolved`` is never reachable through a plain read — resolving a
  hashed principal to a person is a separate, explicit, recorded action by a
  permitted role (:func:`resolve_identity`);
* ``content`` is only visible when the store actually holds content (the default
  fleet profile, ``privacy.mode=metadata-only``, stores none).

This module enforces and records; it does not authenticate. Role assignment in a
real fleet is a managed-policy concern owned by 29.DEP-1 (PRD 50, WS-B); the
:data:`DEFAULT_FLEET_PROFILE` here is the least-privileged posture that path must
adopt, and is kept as a clear interface rather than a second policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from agentwatch.configuration import AgentwatchConfig
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore
from agentwatch.store_access import STORE_ACCESS_TOOL

ACCESS_READ_COMMAND = "access-read"
ACCESS_RESOLVE_COMMAND = "access-resolve"
ACCESS_COMMANDS: tuple[str, ...] = (ACCESS_READ_COMMAND, ACCESS_RESOLVE_COMMAND)

_CONTENT_MODES = frozenset(
    {RecordPrivacyMode.TRUNCATED, RecordPrivacyMode.HASHED, RecordPrivacyMode.FULL}
)


class Role(str, Enum):
    """The reader's role in a fleet/multi-user deployment."""

    SELF = "self"
    TEAM_REVIEWER = "team-reviewer"
    SECURITY_AUDITOR = "security-auditor"
    ADMIN = "admin"


class DataClass(str, Enum):
    """A field-fidelity class a reader may request."""

    METADATA = "metadata"
    IDENTITY_HASHED = "identity-hashed"
    IDENTITY_RESOLVED = "identity-resolved"
    CONTENT = "content"
    EVIDENCE = "evidence"


#: Cross-user grants: ``role -> data-class -> may read``. The ``self`` row has no
#: cross-user grant (a plain user reads only their own records); the owner path is
#: handled separately in :func:`evaluate_access`. Content/evidence grants are
#: further narrowed at evaluation time (content availability, team scope).
ACCESS_MATRIX: dict[Role, dict[DataClass, bool]] = {
    Role.SELF: {data: False for data in DataClass},
    Role.TEAM_REVIEWER: {
        DataClass.METADATA: True,
        DataClass.IDENTITY_HASHED: True,
        DataClass.IDENTITY_RESOLVED: False,
        DataClass.CONTENT: True,
        DataClass.EVIDENCE: True,
    },
    Role.SECURITY_AUDITOR: {data: True for data in DataClass},
    Role.ADMIN: {data: True for data in DataClass},
}

#: Roles permitted to resolve a hashed principal to a person.
RESOLUTION_ROLES = frozenset({Role.SECURITY_AUDITOR, Role.ADMIN})


@dataclass(frozen=True)
class FleetProfile:
    """The storage posture a fleet profile implies (least-privileged by default)."""

    name: str
    privacy_mode: str
    identity: str
    stores_content: bool
    hashes_identity: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "privacy_mode": self.privacy_mode,
            "identity": self.identity,
            "stores_content": self.stores_content,
            "hashes_identity": self.hashes_identity,
        }


#: The default fleet profile: metadata-only, identity hashed, no content stored.
DEFAULT_FLEET_PROFILE = FleetProfile(
    name="least-privileged",
    privacy_mode="metadata-only",
    identity="hashed",
    stores_content=False,
    hashes_identity=True,
)


def fleet_profile_from_config(config: AgentwatchConfig) -> FleetProfile:
    """Derive the effective fleet profile from the live configuration.

    The default config (``privacy.mode=metadata-only``) resolves to the
    least-privileged profile; a non-default posture is named ``extended`` so it is
    never mistaken for the default.
    """
    mode = config.privacy.mode
    return FleetProfile(
        name="least-privileged" if mode == "metadata-only" else "extended",
        privacy_mode=mode,
        identity="hashed" if mode != "full" else "plaintext",
        stores_content=mode != "metadata-only",
        hashes_identity=mode != "full",
    )


@dataclass(frozen=True)
class AccessDecision:
    """The verdict for one (role, data-class, owner, reader) request."""

    role: Role
    data_class: DataClass
    owner: str
    reader: str
    allowed: bool
    reason: str
    action: str
    same_team: bool = False

    @property
    def cross_user(self) -> bool:
        return self.reader != self.owner

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "data_class": self.data_class.value,
            "owner": self.owner,
            "reader": self.reader,
            "allowed": self.allowed,
            "reason": self.reason,
            "action": self.action,
            "same_team": self.same_team,
            "cross_user": self.cross_user,
        }


@dataclass(frozen=True)
class AccessResult:
    """A read/resolution outcome: the decision, the projected fields, the record seq."""

    decision: AccessDecision
    fields: dict[str, Any]
    seq: int | None = None


@dataclass(frozen=True)
class AccessEntry:
    """One stored access record, for the self-visible log."""

    seq: int
    owner: str
    reader: str
    role: Role
    data_class: DataClass
    action: str
    allowed: bool
    reason: str
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "owner": self.owner,
            "reader": self.reader,
            "role": self.role.value,
            "data_class": self.data_class.value,
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
            "at": self.at.isoformat(),
        }


def _as_role(value: Role | str) -> Role:
    return value if isinstance(value, Role) else Role(value)


def _as_data_class(value: DataClass | str) -> DataClass:
    return value if isinstance(value, DataClass) else DataClass(value)


def evaluate_access(
    role: Role | str,
    data_class: DataClass | str,
    *,
    owner: str,
    reader: str,
    same_team: bool = False,
    content_available: bool = False,
    action: str = "read",
) -> AccessDecision:
    """Evaluate one request against the matrix (no I/O; never raises on denial)."""
    resolved_role = _as_role(role)
    resolved_class = _as_data_class(data_class)
    if action not in {"read", "resolve-identity"}:
        raise ValueError(f"unknown access action {action!r}")

    def verdict(allowed: bool, reason: str) -> AccessDecision:
        return AccessDecision(
            role=resolved_role,
            data_class=resolved_class,
            owner=owner,
            reader=reader,
            allowed=allowed,
            reason=reason,
            action=action,
            same_team=same_team,
        )

    if action == "resolve-identity":
        if resolved_class is not DataClass.IDENTITY_RESOLVED:
            return verdict(False, "identity resolution applies only to identity-resolved")
        if resolved_role not in RESOLUTION_ROLES and not (
            resolved_role is Role.SELF and reader == owner
        ):
            return verdict(
                False,
                f"role {resolved_role.value} may not resolve identity; "
                "permitted roles: security-auditor, admin",
            )
        return verdict(True, f"role {resolved_role.value} resolved identity (recorded)")

    if resolved_class is DataClass.IDENTITY_RESOLVED:
        return verdict(
            False,
            "identity-resolved is never reachable by a plain read; "
            "use an explicit, recorded resolve action",
        )

    if reader == owner:
        if resolved_class is DataClass.CONTENT and not content_available:
            return verdict(False, "content is not stored (privacy.mode=metadata-only)")
        return verdict(True, "owner reads their own record")

    if not ACCESS_MATRIX[resolved_role].get(resolved_class, False):
        return verdict(
            False,
            f"role {resolved_role.value} has no cross-user grant for {resolved_class.value}",
        )
    if resolved_class is DataClass.CONTENT and not content_available:
        return verdict(False, "content is not stored (privacy.mode=metadata-only)")
    if (
        resolved_class in {DataClass.CONTENT, DataClass.EVIDENCE}
        and resolved_role is Role.TEAM_REVIEWER
        and not same_team
    ):
        return verdict(False, "team-reviewer is scoped to their own team")
    return verdict(True, f"role {resolved_role.value} is permitted {resolved_class.value}")


def _record_stores_content(record: AgentRecord) -> bool:
    return record.tool.privacy_mode in _CONTENT_MODES


def _project(record: AgentRecord, data_class: DataClass) -> dict[str, Any]:
    """The fields a permitted reader sees for one data class (never more)."""
    if data_class in {DataClass.METADATA, DataClass.EVIDENCE}:
        return {
            "session_id": record.session_id,
            "tool": record.tool.name,
            "outcome": record.outcome.value,
            "started_at": record.started_at.isoformat(),
            "host": record.host,
            "project": record.project,
        }
    if data_class is DataClass.IDENTITY_HASHED:
        return {
            "principal": record.agent.principal,
            "delegation_chain": list(record.agent.delegation_chain or ()),
        }
    if data_class is DataClass.CONTENT:
        return {
            "arguments": record.tool.arguments or {},
            "response": record.tool.response or {},
        }
    return {}


def record_access_decision(
    store: RecordStore,
    decision: AccessDecision,
    *,
    now: datetime | None = None,
    always: bool = False,
) -> AccessEntry | None:
    """Append one metadata-only ``store-access`` record for the decision.

    A same-owner read is not a cross-user read, so it is not recorded unless
    ``always`` (identity resolution is always an explicit, recorded action).
    """
    if not always and not decision.cross_user:
        return None
    command = (
        ACCESS_RESOLVE_COMMAND
        if decision.action == "resolve-identity"
        else ACCESS_READ_COMMAND
    )
    moment = now or datetime.now(timezone.utc)
    arguments: dict[str, Any] = {
        "command": command,
        "scope": {"owner": decision.owner},
        "reader": decision.reader,
        "role": decision.role.value,
        "data_class": decision.data_class.value,
        "action": decision.action,
        "allowed": decision.allowed,
        "reason": decision.reason,
    }
    record = AgentRecord(
        session_id="agentwatch",
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=STORE_ACCESS_TOOL,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK if decision.allowed else Outcome.DENIED,
        started_at=moment,
        producer=MARKER_PRODUCER,
    )
    entry = store.append(record)
    return AccessEntry(
        seq=entry.seq,
        owner=decision.owner,
        reader=decision.reader,
        role=decision.role,
        data_class=decision.data_class,
        action=decision.action,
        allowed=decision.allowed,
        reason=decision.reason,
        at=moment,
    )


def read_fields(
    store: RecordStore,
    record: AgentRecord,
    *,
    role: Role | str,
    data_class: DataClass | str,
    owner: str,
    reader: str,
    same_team: bool = False,
    content_available: bool | None = None,
    now: datetime | None = None,
) -> AccessResult:
    """Read one record's fields under the matrix; deny -> nothing, and record it."""
    resolved_class = _as_data_class(data_class)
    available = _record_stores_content(record) if content_available is None else content_available
    decision = evaluate_access(
        role,
        resolved_class,
        owner=owner,
        reader=reader,
        same_team=same_team,
        content_available=available,
    )
    entry = record_access_decision(store, decision, now=now)
    fields = _project(record, resolved_class) if decision.allowed else {}
    return AccessResult(decision=decision, fields=fields, seq=entry.seq if entry else None)


def resolve_identity(
    store: RecordStore,
    *,
    role: Role | str,
    owner: str,
    reader: str,
    handle: str,
    resolved: str,
    same_team: bool = False,
    now: datetime | None = None,
) -> AccessResult:
    """An explicit, recorded resolution of a hashed principal to a person.

    The caller supplies ``resolved`` (from an identity directory); agentwatch
    never reverses the hash. A role that may not resolve receives nothing and the
    refusal is recorded.
    """
    decision = evaluate_access(
        role,
        DataClass.IDENTITY_RESOLVED,
        owner=owner,
        reader=reader,
        same_team=same_team,
        action="resolve-identity",
    )
    entry = record_access_decision(store, decision, now=now, always=True)
    fields = {"handle": handle, "resolved": resolved} if decision.allowed else {}
    return AccessResult(decision=decision, fields=fields, seq=entry.seq if entry else None)


def access_log(store: RecordStore, *, owner: str) -> list[AccessEntry]:
    """Every recorded access to ``owner``'s records, in store order."""
    entries: list[AccessEntry] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != STORE_ACCESS_TOOL:
            continue
        arguments = record.tool.arguments or {}
        if arguments.get("command") not in ACCESS_COMMANDS:
            continue
        scope = arguments.get("scope")
        scope = scope if isinstance(scope, dict) else {}
        if scope.get("owner") != owner:
            continue
        entries.append(
            AccessEntry(
                seq=entry.seq,
                owner=owner,
                reader=str(arguments.get("reader", "")),
                role=Role(str(arguments.get("role", Role.SELF.value))),
                data_class=DataClass(str(arguments.get("data_class", DataClass.METADATA.value))),
                action=str(arguments.get("action", "read")),
                allowed=bool(arguments.get("allowed", False)),
                reason=str(arguments.get("reason", "")),
                at=record.started_at,
            )
        )
    return entries


def access_log_to_json(owner: str, entries: list[AccessEntry]) -> dict[str, Any]:
    return {"owner": owner, "accesses": [entry.to_dict() for entry in entries]}


def render_access_log(owner: str, entries: list[AccessEntry]) -> str:
    lines = [f"agentwatch access log (owner {owner}): {len(entries)} access(es)"]
    if not entries:
        return "\n".join(lines)
    lines.append("SEQ\tAT\tROLE\tREADER\tACTION\tDATA-CLASS\tALLOWED")
    for entry in entries:
        lines.append(
            f"{entry.seq}\t{entry.at.isoformat()}\t{entry.role.value}\t{entry.reader}\t"
            f"{entry.action}\t{entry.data_class.value}\t{str(entry.allowed).lower()}"
        )
    return "\n".join(lines)


def render_matrix() -> str:
    """A publishable role x data-class table."""
    classes = list(DataClass)
    lines = ["role\t" + "\t".join(data.value for data in classes)]
    for role in Role:
        row = [role.value]
        row.extend("yes" if ACCESS_MATRIX[role][data] else "no" for data in classes)
        lines.append("\t".join(row))
    return "\n".join(lines)


def matrix_to_json() -> dict[str, dict[str, bool]]:
    """The matrix as nested JSON-serializable dicts."""
    return {
        role.value: {data.value: ACCESS_MATRIX[role][data] for data in DataClass} for role in Role
    }


__all__ = [
    "ACCESS_COMMANDS",
    "ACCESS_MATRIX",
    "ACCESS_READ_COMMAND",
    "ACCESS_RESOLVE_COMMAND",
    "DEFAULT_FLEET_PROFILE",
    "RESOLUTION_ROLES",
    "AccessDecision",
    "AccessEntry",
    "AccessResult",
    "DataClass",
    "FleetProfile",
    "Role",
    "access_log",
    "access_log_to_json",
    "evaluate_access",
    "fleet_profile_from_config",
    "matrix_to_json",
    "read_fields",
    "record_access_decision",
    "render_access_log",
    "render_matrix",
    "resolve_identity",
]
