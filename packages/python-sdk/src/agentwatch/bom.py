"""``agentwatch bom`` — an Agent Bill of Materials (M15 S9, #233).

Supply-chain questions about an agent — *which models, MCP servers, tool surface,
and prompt/ruleset version did it have?* — are answerable from data agentwatch
already stores. Rendered as CycloneDX (ECMA-424, with ML-BOM/SaaSBOM component
types) it becomes an artifact procurement, security review, and compliance consume.

The BOM is **observed during recorded sessions**, never "installed on this
machine": a mandatory ``coverage`` block states the basis, window, and non-claims.
Derived read, local, open standard — no new capture, no egress.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentwatch.capabilities import (
    CAP_KIND_COMMAND,
    CAP_KIND_HOOK,
    CAP_KIND_MCP,
    CAP_KIND_MEMORY,
    CAP_KIND_PLUGIN,
    CAP_KIND_RULES,
    CAP_KIND_SKILL,
    CAP_KIND_SUBAGENT,
    Capability,
)
from agentwatch.records import AgentRecord, effective_producer
from agentwatch.store import RecordStore

CYCLONEDX_SPEC_VERSION = "1.5"
BOM_FORMAT = "agentwatch-bom/1"

# Pinned CycloneDX component types used here.
_MODEL = "machine-learning-model"
_SERVICE = "service"
_DATA = "data"
_APPLICATION = "application"
_LIBRARY = "library"

# Capability kind -> CycloneDX component type (M30 CAP-1).
_CAPABILITY_TYPES: dict[str, str] = {
    CAP_KIND_SKILL: _DATA,
    CAP_KIND_PLUGIN: _LIBRARY,
    CAP_KIND_HOOK: _LIBRARY,
    CAP_KIND_SUBAGENT: _APPLICATION,
    CAP_KIND_COMMAND: _APPLICATION,
    CAP_KIND_RULES: _DATA,
    CAP_KIND_MCP: _SERVICE,
    CAP_KIND_MEMORY: _DATA,
}


@dataclass(frozen=True)
class BomComponent:
    """One BOM component, with optional CycloneDX properties."""

    type: str
    name: str
    version: str | None = None
    properties: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, object] = {"type": self.type, "name": self.name}
        if self.version is not None:
            data["version"] = self.version
        if self.properties:
            data["properties"] = [{"name": n, "value": v} for n, v in self.properties]
        return data


@dataclass(frozen=True)
class BomCoverage:
    """The mandatory honesty block: what this BOM observed and does not claim."""

    basis: str
    records: int
    sessions: tuple[str, ...]
    window_start: datetime | None
    window_end: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis,
            "records": self.records,
            "sessions": list(self.sessions),
            "window": {
                "start": self.window_start.isoformat() if self.window_start else None,
                "end": self.window_end.isoformat() if self.window_end else None,
            },
            "claims": "observed during recorded sessions",
            "does_not_claim": [
                "installed on this machine",
                "complete over unrecorded sessions",
                "authoritative for any host not represented here",
            ],
        }


@dataclass(frozen=True)
class Bom:
    """An observed Agent Bill of Materials."""

    components: tuple[BomComponent, ...]
    coverage: BomCoverage
    agentwatch_version: str


def _tool_surface_digest(tools: set[str]) -> str:
    payload = ",".join(sorted(tools)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _agentwatch_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.1.0"


def _selected(record: AgentRecord, *, session_id: str | None, project: str | None) -> bool:
    return (session_id is None or record.session_id == session_id) and (
        project is None or record.project == project
    )


def _capability_components(capabilities: tuple[Capability, ...]) -> list[BomComponent]:
    """Capabilities (M30 CAP-1) as CycloneDX components — digest, never content."""
    components: list[BomComponent] = []
    for capability in capabilities:
        components.append(
            BomComponent(
                type=_CAPABILITY_TYPES.get(capability.kind, _DATA),
                name=capability.name,
                version=capability.declared_version,
                properties=(
                    ("agentwatch:capability-kind", capability.kind),
                    ("agentwatch:capability-scope", capability.scope),
                    ("agentwatch:capability-digest", capability.digest),
                ),
            )
        )
    return components


def build_bom(
    store: RecordStore,
    *,
    session_id: str | None = None,
    project: str | None = None,
    capabilities: tuple[Capability, ...] | None = None,
) -> Bom:
    """Derive an observed BOM from the store (optionally one session/project).

    When ``capabilities`` is given (M30 CAP-1), each is added as a component
    carrying its kind, origin scope and content digest — metadata only.
    """
    records = [
        record
        for record in store.records()
        if _selected(record, session_id=session_id, project=project)
    ]

    models: dict[tuple[str | None, str], None] = {}
    servers: dict[str, set[str]] = {}
    prompts: set[str] = set()
    harnesses: dict[str, set[str]] = {}
    sessions: set[str] = set()
    window_start: datetime | None = None
    window_end: datetime | None = None

    for record in records:
        sessions.add(record.session_id)
        if window_start is None or record.started_at < window_start:
            window_start = record.started_at
        if window_end is None or record.started_at > window_end:
            window_end = record.started_at
        if record.agent.model_version:
            models[(record.agent.name, record.agent.model_version)] = None
        if record.tool.server:
            servers.setdefault(record.tool.server, set()).add(record.tool.name)
        if record.agent.prompt_version:
            prompts.add(record.agent.prompt_version)
        if record.harness:
            producer = effective_producer(record)
            harnesses.setdefault(record.harness, set()).add(producer.kind.value)

    components: list[BomComponent] = []
    for name, version in sorted(models, key=lambda item: (item[0] or "", item[1])):
        components.append(BomComponent(type=_MODEL, name=name or "model", version=version))
    for server in sorted(servers):
        tools = servers[server]
        components.append(
            BomComponent(
                type=_SERVICE,
                name=server,
                properties=(
                    ("agentwatch:observed-tools", ",".join(sorted(tools))),
                    ("agentwatch:tool-surface-digest", _tool_surface_digest(tools)),
                ),
            )
        )
    for prompt_version in sorted(prompts):
        components.append(BomComponent(type=_DATA, name="prompt/ruleset", version=prompt_version))
    for harness in sorted(harnesses):
        components.append(
            BomComponent(
                type=_APPLICATION,
                name=harness,
                properties=(("agentwatch:producer-kinds", ",".join(sorted(harnesses[harness]))),),
            )
        )
    if capabilities:
        components.extend(_capability_components(tuple(capabilities)))
    components.append(BomComponent(type=_LIBRARY, name="agentwatch", version=_agentwatch_version()))

    coverage = BomCoverage(
        basis="observed",
        records=len(records),
        sessions=tuple(sorted(sessions)),
        window_start=window_start,
        window_end=window_end,
    )
    return Bom(
        components=tuple(components),
        coverage=coverage,
        agentwatch_version=_agentwatch_version(),
    )


def to_cyclonedx(bom: Bom) -> dict[str, Any]:
    """Render a BOM as a CycloneDX 1.5 document (coverage under metadata.properties)."""
    properties = [{"name": "agentwatch:coverage", "value": json.dumps(bom.coverage.to_dict())}]
    present_types = {component.type for component in bom.components}
    if _MODEL not in present_types:
        properties.append({"name": "agentwatch:models", "value": "none observed"})
    if _SERVICE not in present_types:
        properties.append({"name": "agentwatch:mcp-servers", "value": "none observed"})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": _APPLICATION,
                "name": "agentwatch-agent-bom",
                "version": bom.agentwatch_version,
            },
            "properties": properties,
        },
        "components": [component.to_dict() for component in bom.components],
    }


def to_agentwatch_json(bom: Bom) -> dict[str, Any]:
    """Render the agentwatch-native JSON shape (coverage as a top-level field)."""
    return {
        "format": BOM_FORMAT,
        "coverage": bom.coverage.to_dict(),
        "components": [component.to_dict() for component in bom.components],
    }


def validate_cyclonedx(document: object) -> list[str]:
    """Structural validation against the CycloneDX 1.5 shape this tool emits.

    Returns a list of problems; empty means valid. This is the same check the
    release verifier applies to a release SBOM (no runtime dependency).
    """
    problems: list[str] = []
    if not isinstance(document, dict):
        return ["document is not an object"]
    if document.get("bomFormat") != "CycloneDX":
        problems.append("bomFormat must be 'CycloneDX'")
    if not isinstance(document.get("specVersion"), str):
        problems.append("specVersion must be a string")
    if not isinstance(document.get("version"), int):
        problems.append("version must be an integer")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("component"), dict):
        problems.append("metadata.component is required")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        problems.append("components must be a non-empty list")
        return problems
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            problems.append(f"components[{index}] is not an object")
            continue
        if not isinstance(component.get("type"), str):
            problems.append(f"components[{index}].type is required")
        if not isinstance(component.get("name"), str):
            problems.append(f"components[{index}].name is required")
    return problems
