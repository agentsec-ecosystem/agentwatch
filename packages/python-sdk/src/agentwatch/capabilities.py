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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

    return CapabilityInventory(capabilities=builder.result(), coverage=_coverage())


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
    "CAP_KINDS",
    "CAP_KIND_COMMAND",
    "CAP_KIND_HOOK",
    "CAP_KIND_MCP",
    "CAP_KIND_MEMORY",
    "CAP_KIND_PLUGIN",
    "CAP_KIND_RULES",
    "CAP_KIND_SKILL",
    "CAP_KIND_SUBAGENT",
    "COVERAGE_EXPOSED",
    "COVERAGE_NONE",
    "COVERAGE_PARTIAL",
    "Capability",
    "CapabilityInventory",
    "CoverageRow",
    "HARNESSES",
    "SCOPES",
    "SCOPE_MANAGED",
    "SCOPE_PLUGIN",
    "SCOPE_PROJECT",
    "SCOPE_USER",
    "capabilities_to_json",
    "discover_capabilities",
    "render_capabilities",
]
