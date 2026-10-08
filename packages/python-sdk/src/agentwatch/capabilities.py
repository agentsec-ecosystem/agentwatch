"""Capability inventory — the 2026 agent supply chain (M30 CAP-1, PRD 52).

Skills, plugins, hooks, subagents, slash commands, rules/instruction files, MCP
servers and (later, DET-7/MEM-1) memory stores are what an agent *loads*, and
they are the surface attackers actually use (Plugin4Shell, ClawHavoc,
ToxicSkills, ``SKILL.md`` poisoning). agentwatch inventories this surface by a
**content digest** — ``sha256`` over the capability's bytes — never by a declared
version, which an attacker can leave unchanged while swapping the body.

Read-only, local, metadata-only. Content is read to hash it and then discarded;
only the digest, size, name, origin scope and (when declared) version are
retained. A digest is not a malware verdict: this module records and diffs, it
never scans or judges. Harness coverage is declared honestly per
``(harness, kind)`` — a gap is ``none``, not silence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    SecurityEvent,
    SecurityEventType,
    StepType,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

# --- capability kinds -------------------------------------------------------

CAP_KIND_SKILL = "skill"
CAP_KIND_PLUGIN = "plugin"
CAP_KIND_HOOK = "hook"
CAP_KIND_SUBAGENT = "subagent"
CAP_KIND_COMMAND = "command"
CAP_KIND_RULES = "rules"
CAP_KIND_MCP = "mcp"
CAP_KIND_MEMORY = "memory"

CAP_KINDS: tuple[str, ...] = (
    CAP_KIND_SKILL,
    CAP_KIND_PLUGIN,
    CAP_KIND_HOOK,
    CAP_KIND_SUBAGENT,
    CAP_KIND_COMMAND,
    CAP_KIND_RULES,
    CAP_KIND_MCP,
    CAP_KIND_MEMORY,
)

# --- origin scopes ----------------------------------------------------------

SCOPE_MANAGED = "managed"
SCOPE_USER = "user"
SCOPE_PROJECT = "project"
SCOPE_PLUGIN = "plugin"

SCOPES: tuple[str, ...] = (SCOPE_MANAGED, SCOPE_USER, SCOPE_PROJECT, SCOPE_PLUGIN)

# --- drift classes (factual wording, never a verdict) -----------------------

CAPABILITY_SNAPSHOT_TOOL = "capability-snapshot"
CAPABILITY_EVENT_TOOL = "capability-changed"
CAPABILITY_LOADED_TOOL = "capability-loaded"

CHANGE_ADDED = "added"
CHANGE_REMOVED = "removed"
CHANGE_VERSION_UNCHANGED = "content changed, version unchanged"
CHANGE_VERSION_CHANGED = "content changed, version changed"
CHANGE_CLASSES: tuple[str, ...] = (
    CHANGE_ADDED,
    CHANGE_REMOVED,
    CHANGE_VERSION_UNCHANGED,
    CHANGE_VERSION_CHANGED,
)

# --- per-harness coverage ---------------------------------------------------

COVERAGE_EXPOSED = "exposed"
COVERAGE_PARTIAL = "partial"
COVERAGE_NONE = "none"

HARNESSES: tuple[str, ...] = ("claude-code", "cursor", "codex-cli", "gemini-cli")

# Claude Code exposes every kind here except memory (MEM-1, a declared gap).
_CLAUDE_EXPOSED = frozenset(
    {
        CAP_KIND_SKILL,
        CAP_KIND_PLUGIN,
        CAP_KIND_HOOK,
        CAP_KIND_SUBAGENT,
        CAP_KIND_COMMAND,
        CAP_KIND_RULES,
        CAP_KIND_MCP,
    }
)

# Memory is discovered as a capability (MEM-1) but its harness layout is not
# pinned, so Claude Code is honestly *partial*.
_CLAUDE_PARTIAL = frozenset({CAP_KIND_MEMORY})

# Standard managed-settings locations (Claude Code). Absent on most machines;
# scanning them is best-effort and never inferred.
_MANAGED_DIRS: tuple[str, ...] = (
    "/Library/Application Support/ClaudeCode",
    "/etc/claude-code",
)

_RULES_FILENAMES: tuple[str, ...] = ("CLAUDE.md", "AGENTS.md")


@dataclass(frozen=True)
class Capability:
    """One loaded capability: digest + metadata, never content."""

    kind: str
    name: str
    scope: str
    digest: str
    size: int
    declared_version: str | None = None
    origin: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "scope": self.scope,
            "digest": self.digest,
            "size": self.size,
            "declared_version": self.declared_version,
        }


@dataclass(frozen=True)
class CoverageRow:
    """Per-``(harness, kind)`` inventory coverage, declared honestly."""

    harness: str
    kind: str
    status: str


@dataclass(frozen=True)
class CapabilityInventory:
    """The discovered capabilities plus the coverage matrix behind them."""

    capabilities: tuple[Capability, ...]
    coverage: tuple[CoverageRow, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Digests (content only, never retained)
# ---------------------------------------------------------------------------


def _digest_path(path: Path) -> tuple[str, int]:
    """Digest a file or directory tree; return ``(sha256, total_size)``.

    A directory is digested over its files in sorted relative-path order, with
    each path and its bytes mixed in, so renames and reorders change the digest.
    The content is read to hash it and immediately discarded.
    """
    if path.is_dir():
        hasher = hashlib.sha256()
        size = 0
        for child in sorted(entry for entry in path.rglob("*") if entry.is_file()):
            relative = child.relative_to(path).as_posix()
            data = child.read_bytes()
            hasher.update(relative.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(data)
            hasher.update(b"\0")
            size += len(data)
        return hasher.hexdigest(), size
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _digest_mapping(value: object) -> tuple[str, int]:
    """Digest a config object (hooks, MCP server) canonically, never retaining it."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class _Builder:
    """Collects capabilities with a deterministic order."""

    def __init__(self) -> None:
        self._items: list[Capability] = []

    def add(self, capability: Capability) -> None:
        self._items.append(capability)

    def add_path(self, kind: str, name: str, scope: str, path: Path, *, version: str | None = None,
                 origin: str | None = None) -> None:
        digest, size = _digest_path(path)
        self.add(
            Capability(
                kind=kind,
                name=name,
                scope=scope,
                digest=digest,
                size=size,
                declared_version=version,
                origin=origin or str(path),
            )
        )

    def add_object(self, kind: str, name: str, scope: str, value: object, *,
                   origin: str | None = None) -> None:
        digest, size = _digest_mapping(value)
        self.add(
            Capability(
                kind=kind,
                name=name,
                scope=scope,
                digest=digest,
                size=size,
                origin=origin,
            )
        )

    def result(self) -> tuple[Capability, ...]:
        return tuple(
            sorted(self._items, key=lambda cap: (cap.kind, cap.scope, cap.name, cap.digest))
        )


def _discover_skills(builder: _Builder, root: Path, scope: str) -> None:
    skills = root / "skills"
    if not skills.is_dir():
        return
    for entry in sorted(skills.iterdir()):
        if entry.is_dir():
            builder.add_path(CAP_KIND_SKILL, entry.name, scope, entry)


def _discover_plugins(builder: _Builder, root: Path, scope: str) -> None:
    plugins = root / "plugins"
    if not plugins.is_dir():
        return
    for entry in sorted(plugins.iterdir()):
        if not entry.is_dir():
            continue
        manifest = _read_json(entry / ".claude-plugin" / "plugin.json")
        name = entry.name
        version: str | None = None
        if isinstance(manifest, dict):
            raw_name = manifest.get("name")
            raw_version = manifest.get("version")
            if isinstance(raw_name, str) and raw_name:
                name = raw_name
            if isinstance(raw_version, str) and raw_version:
                version = raw_version
        builder.add_path(CAP_KIND_PLUGIN, name, scope, entry, version=version)


def _discover_markdown(builder: _Builder, root: Path, subdir: str, kind: str, scope: str) -> None:
    directory = root / subdir
    if not directory.is_dir():
        return
    for entry in sorted(directory.rglob("*.md")):
        if entry.is_file():
            builder.add_path(kind, entry.stem, scope, entry)


def _discover_rules(
    builder: _Builder, root: Path, scope: str, *, project_root: Path | None
) -> None:
    if project_root is not None:
        for filename in _RULES_FILENAMES:
            candidate = project_root / filename
            if candidate.is_file():
                builder.add_path(CAP_KIND_RULES, filename, scope, candidate)
    rules_dir = root / "rules"
    if rules_dir.is_dir():
        for entry in sorted(rules_dir.rglob("*.md")):
            if entry.is_file():
                builder.add_path(CAP_KIND_RULES, entry.stem, scope, entry)


def _discover_hooks(builder: _Builder, settings: Path, scope: str) -> None:
    data = _read_json(settings)
    if not isinstance(data, dict):
        return
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in sorted(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher")
            name = f"{event}:{matcher}" if isinstance(matcher, str) and matcher else f"{event}:*"
            builder.add_object(CAP_KIND_HOOK, name, scope, group, origin=str(settings))


def _discover_mcp(builder: _Builder, config: Path, scope: str) -> None:
    data = _read_json(config)
    if not isinstance(data, dict):
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return
    for name in sorted(servers):
        builder.add_object(CAP_KIND_MCP, name, scope, servers[name], origin=str(config))


def _coverage() -> tuple[CoverageRow, ...]:
    rows: list[CoverageRow] = []
    for harness in HARNESSES:
        for kind in CAP_KINDS:
            if harness == "claude-code" and kind in _CLAUDE_EXPOSED:
                status = COVERAGE_EXPOSED
            elif harness == "claude-code" and kind in _CLAUDE_PARTIAL:
                status = COVERAGE_PARTIAL
            else:
                status = COVERAGE_NONE
            rows.append(CoverageRow(harness=harness, kind=kind, status=status))
    return tuple(rows)


def discover_capabilities(
    *, project: Path | None = None, home: Path | None = None
) -> CapabilityInventory:
    """Inventory loadable capabilities under a home and a project (Claude Code).

    ``project`` and ``home`` default to the current working directory and the
    user's home. Missing directories are not an error — a kind that is absent is
    simply absent, and the coverage matrix states what was and was not read.
    """
    resolved_home = (home or Path.home()).expanduser()
    resolved_project = (project or Path.cwd()).expanduser()
    builder = _Builder()

    claude_home = resolved_home / ".claude"
    claude_project = resolved_project / ".claude"

    # user scope
    _discover_skills(builder, claude_home, SCOPE_USER)
    _discover_plugins(builder, claude_home, SCOPE_USER)
    _discover_markdown(builder, claude_home, "agents", CAP_KIND_SUBAGENT, SCOPE_USER)
    _discover_markdown(builder, claude_home, "commands", CAP_KIND_COMMAND, SCOPE_USER)
    _discover_rules(builder, claude_home, SCOPE_USER, project_root=None)
    _discover_hooks(builder, claude_home / "settings.json", SCOPE_USER)
    _discover_mcp(builder, resolved_home / ".claude.json", SCOPE_USER)

    # project scope
    _discover_skills(builder, claude_project, SCOPE_PROJECT)
    _discover_plugins(builder, claude_project, SCOPE_PROJECT)
    _discover_markdown(builder, claude_project, "agents", CAP_KIND_SUBAGENT, SCOPE_PROJECT)
    _discover_markdown(builder, claude_project, "commands", CAP_KIND_COMMAND, SCOPE_PROJECT)
    _discover_rules(builder, claude_project, SCOPE_PROJECT, project_root=resolved_project)
    _discover_hooks(builder, claude_project / "settings.json", SCOPE_PROJECT)
    _discover_mcp(builder, resolved_project / ".mcp.json", SCOPE_PROJECT)

    # managed scope (best-effort; absent on most machines)
    for managed in _MANAGED_DIRS:
        managed_dir = Path(managed)
        if not managed_dir.is_dir():
            continue
        _discover_skills(builder, managed_dir, SCOPE_MANAGED)
        _discover_plugins(builder, managed_dir, SCOPE_MANAGED)
        _discover_hooks(builder, managed_dir / "managed-settings.json", SCOPE_MANAGED)
        _discover_mcp(builder, managed_dir / "managed-mcp.json", SCOPE_MANAGED)

    # Memory stores are capabilities too (MEM-1); imported lazily to avoid a
    # module cycle (memory reuses Capability).
    from agentwatch.memory import discover_memory_capabilities

    for capability in discover_memory_capabilities(
        home=resolved_home, project=resolved_project
    ):
        builder.add(capability)

    return CapabilityInventory(capabilities=builder.result(), coverage=_coverage())


# ---------------------------------------------------------------------------
# Snapshot & drift (M30 CAP-2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityState:
    """One session's capability set as recorded in a carrier."""

    session_id: str
    at: datetime
    capabilities: tuple[Capability, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "at": self.at.isoformat(),
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }


@dataclass(frozen=True)
class CapabilityChange:
    """A factual change between two sessions' capability sets."""

    kind: str
    name: str
    scope: str
    change: str
    prev_digest: str | None
    digest: str | None
    prev_declared_version: str | None
    declared_version: str | None
    session_id: str
    prev_session_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "scope": self.scope,
            "change": self.change,
            "prev_digest": self.prev_digest,
            "digest": self.digest,
            "prev_declared_version": self.prev_declared_version,
            "declared_version": self.declared_version,
            "session_id": self.session_id,
            "prev_session_id": self.prev_session_id,
        }


def _sorted_capabilities(capabilities: Sequence[Capability]) -> tuple[Capability, ...]:
    return tuple(sorted(capabilities, key=lambda cap: (cap.kind, cap.scope, cap.name, cap.digest)))


def snapshot_records(
    session_id: str, capabilities: Sequence[Capability], *, at: datetime
) -> list[AgentRecord]:
    """One metadata-only ``capability-snapshot`` carrier for a session.

    The carrier holds the *entire* set (a list of kind/name/scope/digest/version
    entries) so that an empty set is still a recorded baseline — absence of a
    capability is a fact, not a missing snapshot.
    """
    payload = [
        {
            "kind": capability.kind,
            "name": capability.name,
            "scope": capability.scope,
            "digest": capability.digest,
            "size": capability.size,
            "declared_version": capability.declared_version,
        }
        for capability in _sorted_capabilities(capabilities)
    ]
    return [
        AgentRecord(
            session_id=session_id,
            agent=AgentIdentity(identity="agentwatch"),
            tool=ToolCall(
                name=CAPABILITY_SNAPSHOT_TOOL,
                arguments={"capabilities": payload},
                privacy_mode=RecordPrivacyMode.METADATA_ONLY,
            ),
            outcome=Outcome.OK,
            started_at=at,
            producer=MARKER_PRODUCER,
            step_type=StepType.OBSERVE,
        )
    ]


def _capability_from_entry(entry: object) -> Capability | None:
    if not isinstance(entry, dict):
        return None
    kind = entry.get("kind")
    name = entry.get("name")
    scope = entry.get("scope")
    digest = entry.get("digest")
    if not all(isinstance(value, str) and value for value in (kind, name, scope, digest)):
        return None
    size = entry.get("size")
    version = entry.get("declared_version")
    return Capability(
        kind=str(kind),
        name=str(name),
        scope=str(scope),
        digest=str(digest),
        size=size if isinstance(size, int) else 0,
        declared_version=version if isinstance(version, str) else None,
    )


def survey_capabilities(records: Sequence[AgentRecord]) -> list[CapabilityState]:
    """Every session's recorded capability set, ordered by first sighting."""
    states: dict[str, CapabilityState] = {}
    for record in records:
        if record.tool.name != CAPABILITY_SNAPSHOT_TOOL:
            continue
        arguments = record.tool.arguments if isinstance(record.tool.arguments, dict) else {}
        raw = arguments.get("capabilities")
        found: list[Capability] = []
        if isinstance(raw, list):
            for entry in raw:
                capability = _capability_from_entry(entry)
                if capability is not None:
                    found.append(capability)
        states[record.session_id] = CapabilityState(
            session_id=record.session_id,
            at=record.started_at,
            capabilities=_sorted_capabilities(found),
        )
    return sorted(states.values(), key=lambda state: (state.at, state.session_id))


def _diff_states(prev: CapabilityState, current: CapabilityState) -> list[CapabilityChange]:
    prev_map = {(cap.kind, cap.name, cap.scope): cap for cap in prev.capabilities}
    current_map = {(cap.kind, cap.name, cap.scope): cap for cap in current.capabilities}
    changes: list[CapabilityChange] = []
    for key in sorted(set(prev_map) | set(current_map)):
        before = prev_map.get(key)
        after = current_map.get(key)
        if before is None:
            change = CHANGE_ADDED
        elif after is None:
            change = CHANGE_REMOVED
        elif before.digest != after.digest:
            change = (
                CHANGE_VERSION_UNCHANGED
                if before.declared_version == after.declared_version
                else CHANGE_VERSION_CHANGED
            )
        else:
            continue
        changes.append(
            CapabilityChange(
                kind=key[0],
                name=key[1],
                scope=key[2],
                change=change,
                prev_digest=before.digest if before else None,
                digest=after.digest if after else None,
                prev_declared_version=before.declared_version if before else None,
                declared_version=after.declared_version if after else None,
                session_id=current.session_id,
                prev_session_id=prev.session_id,
            )
        )
    return changes


def detect_capability_changes(
    records: Sequence[AgentRecord], *, since: datetime | None = None
) -> list[CapabilityChange]:
    """Consecutive-session capability changes across the recorded carriers."""
    states = survey_capabilities(records)
    if since is not None:
        states = [state for state in states if state.at >= since]
    changes: list[CapabilityChange] = []
    for prev, current in zip(states, states[1:], strict=False):
        changes.extend(_diff_states(prev, current))
    return changes


def capability_event(change: CapabilityChange, *, at: datetime) -> SecurityEvent:
    """The ``capability-changed`` observation for one factual change."""
    return SecurityEvent(
        type=SecurityEventType.CAPABILITY_CHANGED,
        emitted_at=at,
        emitter="agentwatch",
        tool=change.name,
        evidence={
            "kind": change.kind,
            "name": change.name,
            "scope": change.scope,
            "change": change.change,
            "prev_digest": change.prev_digest,
            "digest": change.digest,
            "prev_declared_version": change.prev_declared_version,
            "declared_version": change.declared_version,
        },
    )


def _change_record(session_id: str, change: CapabilityChange, at: datetime) -> AgentRecord:
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(name=CAPABILITY_EVENT_TOOL),
        outcome=Outcome.OK,
        started_at=at,
        producer=MARKER_PRODUCER,
        step_type=StepType.OBSERVE,
        security_event=capability_event(change, at=at),
    )


def record_capability_snapshot(
    store: RecordStore,
    session_id: str,
    capabilities: Sequence[Capability],
    *,
    now: datetime | None = None,
) -> list[CapabilityChange]:
    """Append a session's capability snapshot and emit one event per change.

    Compares against the latest prior snapshot; a first snapshot emits nothing
    (there is no baseline to diff against).
    """
    moment = now or datetime.now(timezone.utc)
    prior = survey_capabilities(store.records())
    current = CapabilityState(
        session_id=session_id, at=moment, capabilities=_sorted_capabilities(capabilities)
    )
    changes = _diff_states(prior[-1], current) if prior else []
    for record in snapshot_records(session_id, capabilities, at=moment):
        store.append(record)
    for change in changes:
        store.append(_change_record(session_id, change, moment))
    return changes


def render_capability_changes(changes: Sequence[CapabilityChange]) -> str:
    if not changes:
        return "no capability changes"
    lines = ["KIND\tSCOPE\tNAME\tCHANGE\tPREV_DIGEST\tDIGEST"]
    for change in changes:
        lines.append(
            f"{change.kind}\t{change.scope}\t{change.name}\t{change.change}\t"
            f"{change.prev_digest or '-'}\t{change.digest or '-'}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Load attribution (M30 CAP-3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityLoad:
    """One metadata-only capability load, as shown to replay/impact/search."""

    name: str
    kind: str
    scope: str
    digest: str | None
    at: datetime
    session_id: str

    def context_line(self) -> str:
        """Factual wording: context, never a causal claim."""
        return f"followed the load of {self.kind} {self.name} ({self.scope})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "scope": self.scope,
            "digest": self.digest,
            "at": self.at.isoformat(),
            "session_id": self.session_id,
        }


def capability_loaded_record(
    session_id: str,
    name: str,
    *,
    kind: str = CAP_KIND_SKILL,
    scope: str = SCOPE_USER,
    digest: str | None = None,
    declared_version: str | None = None,
    at: datetime | None = None,
) -> AgentRecord:
    """A metadata-only ``capability-loaded`` step (name/kind/scope/digest)."""
    arguments: dict[str, Any] = {"kind": kind, "name": name, "scope": scope}
    if digest is not None:
        arguments["digest"] = digest
    if declared_version is not None:
        arguments["declared_version"] = declared_version
    return AgentRecord(
        session_id=session_id,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=CAPABILITY_LOADED_TOOL,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=Outcome.OK,
        started_at=at or datetime.now(timezone.utc),
        producer=MARKER_PRODUCER,
        step_type=StepType.OBSERVE,
    )


def record_capability_load(
    store: RecordStore,
    session_id: str,
    name: str,
    *,
    kind: str = CAP_KIND_SKILL,
    scope: str = SCOPE_USER,
    digest: str | None = None,
    declared_version: str | None = None,
    at: datetime | None = None,
) -> CapabilityLoad:
    """Append a metadata-only load step and return the load fact."""
    moment = at or datetime.now(timezone.utc)
    record = capability_loaded_record(
        session_id,
        name,
        kind=kind,
        scope=scope,
        digest=digest,
        declared_version=declared_version,
        at=moment,
    )
    store.append(record)
    return CapabilityLoad(
        name=name, kind=kind, scope=scope, digest=digest, at=moment, session_id=session_id
    )


def _load_from_record(record: AgentRecord) -> CapabilityLoad | None:
    if record.tool.name != CAPABILITY_LOADED_TOOL:
        return None
    arguments = record.tool.arguments
    if not isinstance(arguments, dict):
        return None
    name = arguments.get("name")
    if not isinstance(name, str) or not name:
        return None
    digest = arguments.get("digest")
    return CapabilityLoad(
        name=name,
        kind=str(arguments.get("kind", "")),
        scope=str(arguments.get("scope", "")),
        digest=digest if isinstance(digest, str) else None,
        at=record.started_at,
        session_id=record.session_id,
    )


def capability_loads(
    records: Sequence[AgentRecord], *, session_id: str | None = None
) -> list[CapabilityLoad]:
    """Every recorded capability load, in store order (optionally one session)."""
    loads: list[CapabilityLoad] = []
    for record in records:
        if session_id is not None and record.session_id != session_id:
            continue
        load = _load_from_record(record)
        if load is not None:
            loads.append(load)
    return loads


def render_capability_loads(loads: Sequence[CapabilityLoad]) -> str:
    if not loads:
        return "no capability loads"
    lines = ["AT\tKIND\tNAME\tSCOPE\tWAS"]
    for load in loads:
        lines.append(
            f"{load.at.isoformat()}\t{load.kind}\t{load.name}\t{load.scope}\t"
            f"{load.context_line()}"
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class LoadExposure:
    """Per-harness capability-load exposure, declared honestly."""

    harness: str
    status: str
    note: str


LOAD_EXPOSURE: tuple[LoadExposure, ...] = (
    LoadExposure(
        "claude-code",
        COVERAGE_PARTIAL,
        "recorded via the capability-loaded API; not auto-emitted from the hook payload yet",
    ),
    LoadExposure("cursor", COVERAGE_NONE, "no load signal exposed"),
    LoadExposure("codex-cli", COVERAGE_NONE, "no load signal exposed"),
    LoadExposure("gemini-cli", COVERAGE_NONE, "no load signal exposed"),
)


def load_exposure_matrix() -> tuple[LoadExposure, ...]:
    """The published, CI-checked load-exposure matrix (one row per harness)."""
    return LOAD_EXPOSURE


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def capabilities_to_json(inventory: CapabilityInventory) -> dict[str, Any]:
    """Stable JSON shape (metadata + digests only; never content)."""
    return {
        "capabilities": [capability.to_dict() for capability in inventory.capabilities],
        "coverage": [
            {"harness": row.harness, "kind": row.kind, "status": row.status}
            for row in inventory.coverage
        ],
    }


def render_capabilities(inventory: CapabilityInventory) -> str:
    """Human-readable capability table."""
    lines = ["KIND\tSCOPE\tNAME\tVERSION\tSIZE\tDIGEST"]
    for capability in inventory.capabilities:
        lines.append(
            f"{capability.kind}\t{capability.scope}\t{capability.name}\t"
            f"{capability.declared_version or '-'}\t{capability.size}\t{capability.digest}"
        )
    return "\n".join(lines)


__all__ = [
    "CAPABILITY_EVENT_TOOL",
    "CAPABILITY_LOADED_TOOL",
    "CAPABILITY_SNAPSHOT_TOOL",
    "CAP_KINDS",
    "CAP_KIND_COMMAND",
    "CAP_KIND_HOOK",
    "CAP_KIND_MCP",
    "CAP_KIND_MEMORY",
    "CAP_KIND_PLUGIN",
    "CAP_KIND_RULES",
    "CAP_KIND_SKILL",
    "CAP_KIND_SUBAGENT",
    "CHANGE_ADDED",
    "CHANGE_CLASSES",
    "CHANGE_REMOVED",
    "CHANGE_VERSION_CHANGED",
    "CHANGE_VERSION_UNCHANGED",
    "COVERAGE_EXPOSED",
    "COVERAGE_NONE",
    "COVERAGE_PARTIAL",
    "Capability",
    "CapabilityChange",
    "CapabilityInventory",
    "CapabilityLoad",
    "CapabilityState",
    "CoverageRow",
    "HARNESSES",
    "LOAD_EXPOSURE",
    "LoadExposure",
    "SCOPES",
    "SCOPE_MANAGED",
    "SCOPE_PLUGIN",
    "SCOPE_PROJECT",
    "SCOPE_USER",
    "capabilities_to_json",
    "capability_event",
    "capability_loaded_record",
    "capability_loads",
    "detect_capability_changes",
    "discover_capabilities",
    "load_exposure_matrix",
    "record_capability_load",
    "record_capability_snapshot",
    "render_capabilities",
    "render_capability_changes",
    "render_capability_loads",
    "snapshot_records",
    "survey_capabilities",
]
