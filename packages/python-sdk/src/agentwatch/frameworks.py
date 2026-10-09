"""Certified framework recipes (M29 FWK-1, PRD 51 §FWK-1, #446).

Frameworks emit OpenTelemetry natively (Google ADK, Strands Agents) or through
community instrumentation (Arize OpenInference for the OpenAI Agents SDK). Rather
than hand-written adapters that drift from every framework release, agentwatch
consumes their OTel through the **shared** :mod:`agentwatch.ingest` transcoder and
holds each recipe in the compatibility matrix with an honest tier.

This module is the single source of truth for the recipe set: the pinned version,
the importable module, the attribute vocabulary (GenAI vs OpenInference), the
identity/step/cost mapping, and the ≤2-line recipe. It is deliberately data-only —
:func:`agentwatch.instrument` (FWK-2) and the compatibility generator both read it.

Honesty: none of these frameworks is installable in the sandbox that builds this
milestone, so no recipe is ``live-verified``. Each fixture is *shape-derived* from
the vendor/community attribute vocabulary and the live pinned run is BLOCKED with
the exact reason carried on the recipe.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from agentwatch.compatibility import FIDELITY_MODELED

# Re-export the tier vocabulary so recipes carry a compatibility-matrix tier.
TIER_MODELED = FIDELITY_MODELED

# Attribute vocabularies a recipe may speak.
SOURCE_GENAI = "otel-genai"
SOURCE_OPENINFERENCE = "openinference"
SOURCE_CLAUDE_CODE = "claude-code-otel"
SOURCES: tuple[str, ...] = (SOURCE_GENAI, SOURCE_OPENINFERENCE, SOURCE_CLAUDE_CODE)

# The exact reason the live pinned run is deferred. Kept as a constant so the doc,
# the recipe and the report cannot drift from one another.
_BLOCKED_NOT_INSTALLABLE = (
    "live pinned run BLOCKED: the framework is not installable in the CI sandbox; "
    "fixture-driven conformance only"
)


@dataclass(frozen=True)
class FrameworkRecipe:
    """One certified framework recipe (data-only; no framework import required)."""

    name: str
    package: str
    module: str
    pinned: str
    source: str
    recipe: str
    identity_keys: tuple[str, ...]
    step_map: Mapping[str, str]
    cost_keys: tuple[str, ...]
    tier: str = TIER_MODELED
    live_verified: bool = False
    blocked_reason: str = _BLOCKED_NOT_INSTALLABLE
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "package": self.package,
            "module": self.module,
            "pinned": self.pinned,
            "source": self.source,
            "recipe": self.recipe,
            "identity_keys": list(self.identity_keys),
            "step_map": dict(self.step_map),
            "cost_keys": list(self.cost_keys),
            "tier": self.tier,
            "live_verified": self.live_verified,
            "blocked_reason": self.blocked_reason,
            "notes": self.notes,
        }


# GenAI cost keys agentwatch consumes (mirrors ``ingest._COST_KEYS``).
_GENAI_COST_KEYS = (
    "gen_ai.usage.cost",
    "gen_ai.usage.total_cost",
)
_OPENINFERENCE_COST_KEYS = ("llm.cost.total",)

_GENAI_STEPS: Mapping[str, str] = {
    "invoke_agent": "agent",
    "invoke_workflow": "workflow",
    "execute_tool": "tool",
    "generate_content": "model",
    "chat": "model",
    "plan": "plan",
    "retrieval": "retrieval",
}
_OPENINFERENCE_STEPS: Mapping[str, str] = {
    "AGENT": "agent",
    "LLM": "model",
    "TOOL": "tool",
    "CHAIN": "chain",
    "RETRIEVER": "retrieval",
}
_CLAUDE_STEPS: Mapping[str, str] = {
    "invoke_agent": "agent",
    "execute_tool": "tool",
}

RECIPES: dict[str, FrameworkRecipe] = {
    "adk": FrameworkRecipe(
        name="adk",
        package="google-adk",
        module="google.adk",
        pinned="1.5.0",
        source=SOURCE_GENAI,
        recipe=(
            "export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector\n"
            "python my_adk_app.py  # ADK emits GenAI spans over OTLP"
        ),
        identity_keys=("gen_ai.agent.name", "service.name"),
        step_map=_GENAI_STEPS,
        cost_keys=_GENAI_COST_KEYS,
        notes="Google ADK native OTel GenAI spans (invoke_agent/invoke_workflow/generate_content).",
    ),
    "strands": FrameworkRecipe(
        name="strands",
        package="strands-agents",
        module="strands",
        pinned="1.0.0",
        source=SOURCE_GENAI,
        recipe=(
            "export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector\n"
            "python my_strands_agent.py  # Strands emits gen_ai.* spans over OTLP"
        ),
        identity_keys=("gen_ai.agent.name", "service.name"),
        step_map=_GENAI_STEPS,
        cost_keys=_GENAI_COST_KEYS,
        notes="Strands Agents OTel-native agent/model/tool spans using the gen_ai.* vocabulary.",
    ),
    "openai-agents": FrameworkRecipe(
        name="openai-agents",
        package="openinference-instrumentation-openai-agents",
        module="openinference.instrumentation.openai_agents",
        pinned="0.1.0",
        source=SOURCE_OPENINFERENCE,
        recipe=(
            "from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor; "
            "OpenAIAgentsInstrumentor().instrument()\n"
            "export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector"
        ),
        identity_keys=("agent.name", "service.name"),
        step_map=_OPENINFERENCE_STEPS,
        cost_keys=_OPENINFERENCE_COST_KEYS,
        notes="OpenAI Agents SDK via OpenInference; openinference.* / llm.* attributes.",
    ),
    "claude-agent-sdk": FrameworkRecipe(
        name="claude-agent-sdk",
        package="claude-agent-sdk",
        module="claude_agent_sdk",
        pinned="0.1.0",
        source=SOURCE_CLAUDE_CODE,
        recipe=(
            "# Claude Agent SDK runs the Claude Code CLI; enable its shared OTel export (CCO-1)\n"
            "export CLAUDE_CODE_ENABLE_TELEMETRY=1 "
            "OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317"
        ),
        identity_keys=("gen_ai.agent.name", "service.name"),
        step_map=_CLAUDE_STEPS,
        cost_keys=_GENAI_COST_KEYS,
        blocked_reason=(
            "live pinned run BLOCKED: depends on 29.CCO-1 (WS-A) Claude Code OTel ingest "
            "(tool_use_id join), which is not on m29/frameworks"
        ),
        notes="Routes through the shared Claude Code OTel path (CCO-1); no duplicate ingest.",
    ),
}

SUPPORTED_FRAMEWORKS: tuple[str, ...] = tuple(sorted(RECIPES))


@dataclass(frozen=True)
class FrameworkDetection:
    """Which supported frameworks are importable in this environment."""

    installed: tuple[str, ...] = ()
    missing: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"installed": list(self.installed), "missing": list(self.missing)}


def get(name: str) -> FrameworkRecipe:
    """Return one recipe (KeyError if it is not a supported framework)."""
    return RECIPES[name]


def all_recipes() -> list[FrameworkRecipe]:
    """Every recipe, deterministically ordered by name."""
    return [RECIPES[name] for name in SUPPORTED_FRAMEWORKS]


def recipe_line_count(name: str) -> int:
    """Count the recipe's non-empty lines (the ≤2-line acceptance)."""
    return len([line for line in RECIPES[name].recipe.splitlines() if line.strip()])


def detect_installed(
    *,
    find_spec: Callable[[str], object] | None = None,
) -> FrameworkDetection:
    """Detect which supported frameworks are importable (never imports them).

    ``find_spec`` is injectable so the FWK-2 auto-detect path can be tested
    without the frameworks installed.
    """
    probe = find_spec or importlib.util.find_spec
    installed: list[str] = []
    missing: list[str] = []
    for name in SUPPORTED_FRAMEWORKS:
        module = RECIPES[name].module
        try:
            found = probe(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            found = False
        (installed if found else missing).append(name)
    return FrameworkDetection(installed=tuple(installed), missing=tuple(missing))


def drift(upstream: Mapping[str, str]) -> list[str]:
    """Compare pinned versions against an upstream version map.

    A pinned recipe whose upstream version moved is drift; a missing upstream
    entry is informational (it is not proof of a change) and never a failure.
    """
    entries: list[str] = []
    for name in SUPPORTED_FRAMEWORKS:
        pinned = RECIPES[name].pinned
        observed = upstream.get(name)
        if observed is not None and observed != pinned:
            entries.append(f"{name}: pinned {pinned} != upstream {observed}")
    return entries


def source_kind(source: str) -> str:
    """Validate and return a source vocabulary tag (fail closed on unknown)."""
    if source not in SOURCES:
        raise ValueError(f"unknown framework source {source!r}; expected one of {SOURCES}")
    return source


__all__ = [
    "FrameworkDetection",
    "FrameworkRecipe",
    "RECIPES",
    "SOURCES",
    "SOURCE_CLAUDE_CODE",
    "SOURCE_GENAI",
    "SOURCE_OPENINFERENCE",
    "SUPPORTED_FRAMEWORKS",
    "TIER_MODELED",
    "all_recipes",
    "detect_installed",
    "drift",
    "get",
    "recipe_line_count",
    "source_kind",
]
