"""Harness compatibility table + version-drift matrix (M10 N4 #215).

Single source of truth for the release compatibility table and the tested version
ranges: the shipped-adapter registry below. A generator renders
``docs/reference/compatibility.md`` from it, and a nightly job fingerprints the
conformance fixtures so a harness shape change is caught before a user reports it.

Fixtures carry a version tag (the harness's tested maximum) and a shape
fingerprint in ``tests/fixtures/harness-versions.json``; adding a field changes
the fingerprint and is surfaced for review (compatible vs. breaking is a human
call — the drift job never edits anything silently).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BEGIN = "<!-- BEGIN GENERATED HARNESS MATRIX -->"
_END = "<!-- END GENERATED HARNESS MATRIX -->"

# Fidelity tiers (XHT-4, PRD 47): how an adapter's support was established, so a
# "modeled" adapter is never mistaken for a captured one.
#   live-verified    — real captures from the running harness, kept current
#   fixture-verified — real captures committed as fixtures, not continuously re-captured
#   modeled          — the event shape is assumed, not captured
FIDELITY_LIVE = "live-verified"
FIDELITY_FIXTURE = "fixture-verified"
FIDELITY_MODELED = "modeled"
FIDELITY_TIERS: tuple[str, ...] = (FIDELITY_LIVE, FIDELITY_FIXTURE, FIDELITY_MODELED)

# Managed-policy status (M29 EXT-7): the honest state of a hook-based recorder
# under Claude Code managed settings (`allowManagedHooksOnly`, etc.).
MANAGED_EFFECTIVE = "effective"
MANAGED_BLOCKED = "blocked"
MANAGED_UNKNOWN = "unknown"
MANAGED_NA = "n/a"
MANAGED_POLICY_STATUSES: tuple[str, ...] = (
    MANAGED_EFFECTIVE,
    MANAGED_BLOCKED,
    MANAGED_UNKNOWN,
    MANAGED_NA,
)


@dataclass(frozen=True)
class HarnessRange:
    """The tested harness-version range (inclusive-ish; ``maximum`` may be a wildcard)."""

    minimum: str
    maximum: str

    def render(self) -> str:
        if self.minimum == self.maximum:
            return self.minimum
        return f"{self.minimum}\u2013{self.maximum}"


@dataclass(frozen=True)
class HarnessInfo:
    """One shipped adapter's compatibility metadata."""

    harness: str
    tier: str
    tested: HarnessRange
    fidelity: str
    invocation: str
    notes: str = ""
    protocol: str = ""
    managed_policy: str = MANAGED_NA
    # A declared tier: support is provisional/modeled and *declared* as such, so it
    # is not a full-fidelity Tier-1 claim (PRD 40 §5.3 "real captures or declared
    # tiers"). Declared rows are exempt from the "no modeled Tier-1 row" gate.
    declared: bool = False


# Adapter metadata registry: the generated table's single source of truth. Every
# shipped adapter must appear here (enforced by tests).
SHIPPED: dict[str, HarnessInfo] = {
    "claude-code": HarnessInfo(
        harness="claude-code",
        tier="Tier-1",
        tested=HarnessRange("2.0", "2.x"),
        fidelity=FIDELITY_LIVE,
        invocation="native hooks (`agentwatch init`)",
        notes=(
            "PreToolUse/PostToolUse + local daemon; under `allowManagedHooksOnly` a "
            "user/project install is blocked — managed hook/plugin path (DEP-1)"
        ),
        managed_policy=MANAGED_BLOCKED,
    ),
    "cursor": HarnessInfo(
        harness="cursor",
        tier="Tier-1",
        tested=HarnessRange("1.7", "1.x"),
        fidelity=FIDELITY_FIXTURE,
        invocation="native hooks (`hooks.json`)",
        notes=(
            "full loop; vendor+MIT fixture corpus (25.CUR-1); live capture pending"
        ),
        managed_policy=MANAGED_UNKNOWN,
    ),
    "codex-cli": HarnessInfo(
        harness="codex-cli",
        tier="Tier-1",
        tested=HarnessRange("0.65", "0.x"),
        fidelity=FIDELITY_FIXTURE,
        invocation="log-reader (`ingest --agent codex`)",
        notes=(
            "rollout JSONL / .jsonl.zst; format-derived + cross-parser validated "
            "(COD-1/XHT-3); live capture pending"
        ),
    ),
    "gemini-cli": HarnessInfo(
        harness="gemini-cli",
        tier="Tier-1",
        tested=HarnessRange("modeled", "modeled"),
        fidelity=FIDELITY_MODELED,
        invocation="native OTel telemetry (`ingest --format otel`)",
        notes=(
            "declared: provisional/modeled shapes (harness-adapters-plan M10 #82); "
            "native approval/principal mapping (GEM-2); real capture pending (v0.3.0 target)"
        ),
        declared=True,
    ),
    "mcp-proxy": HarnessInfo(
        harness="mcp-proxy",
        tier="proxy",
        tested=HarnessRange("2026-07-28", "2026-07-28"),
        fidelity=FIDELITY_LIVE,
        invocation="`agentwatch mcp-proxy` / `init --mcp-proxy`",
        notes=(
            "MCP JSON-RPC full surface (tools/resources/prompts/elicitation/tasks), Streamable HTTP"
        ),
        protocol="2026-07-28",
    ),
    "a2a-proxy": HarnessInfo(
        harness="a2a-proxy",
        tier="proxy",
        tested=HarnessRange("1.0", "1.0"),
        fidelity=FIDELITY_FIXTURE,
        invocation="`agentwatch a2a-proxy` / `a2aAgents` install",
        notes=(
            "A2A tasks/messages/artifacts + signed agent cards; deterministic card "
            "provenance; agent-delegation observation; declared gaps relayed"
        ),
        protocol="1.0",
    ),
    "crewai": HarnessInfo(
        harness="crewai",
        tier="Tier-2",
        tested=HarnessRange("modeled", "modeled"),
        fidelity=FIDELITY_MODELED,
        invocation="native adapter (modeled)",
    ),
    "pydantic-ai": HarnessInfo(
        harness="pydantic-ai",
        tier="Tier-2",
        tested=HarnessRange("modeled", "modeled"),
        fidelity=FIDELITY_MODELED,
        invocation="native adapter (modeled)",
    ),
}

# Instrumentation-framework rows (input for WS-D / FWK-1, #446). These are not
# shipped harness adapters, so they stay out of ``SHIPPED``; the generator
# renders them alongside adapter rows once WS-D fills in recipes + mappings.
FRAMEWORKS: dict[str, HarnessInfo] = {
    "adk": HarnessInfo(
        harness="adk",
        tier="Tier-2",
        tested=HarnessRange("1.5.0", "1.x"),
        fidelity=FIDELITY_MODELED,
        invocation="OTel GenAI over OTLP (`agentwatch ingest --format otel`)",
        notes="Google ADK native spans; fixture-driven, live run BLOCKED (not installable here)",
    ),
    "strands": HarnessInfo(
        harness="strands",
        tier="Tier-2",
        tested=HarnessRange("1.0.0", "1.x"),
        fidelity=FIDELITY_MODELED,
        invocation="OTel GenAI over OTLP (`agentwatch ingest --format otel`)",
        notes="Strands native spans; fixture-driven, live run BLOCKED (not installable here)",
    ),
    "openai-agents": HarnessInfo(
        harness="openai-agents",
        tier="Tier-2",
        tested=HarnessRange("0.1.0", "0.x"),
        fidelity=FIDELITY_MODELED,
        invocation="OpenInference → OTLP (`agentwatch ingest --format otel`)",
        notes=(
            "OpenAI Agents SDK via OpenInference; fixture-driven, live run BLOCKED "
            "(not installable here)"
        ),
    ),
    "claude-agent-sdk": HarnessInfo(
        harness="claude-agent-sdk",
        tier="Tier-2",
        tested=HarnessRange("0.1.0", "0.x"),
        fidelity=FIDELITY_MODELED,
        invocation="shared Claude Code OTel (`ingest --format claude-otel`, `sdk-native`)",
        notes="Routes through 29.CCO-1 (WS-A); tool_use_id join owned by CCO-1, live run BLOCKED",
    ),
}

# Every row the generated table renders: shipped adapters + framework recipes.
ALL_ROWS: dict[str, HarnessInfo] = {**SHIPPED, **FRAMEWORKS}

_TABLE_HEADER = (
    "| Harness | Tier | Tested range | Protocol | Fidelity | Managed policy | Invocation "
    "| Notes |\n"
    "|---|---|---|---|---|---|---|---|"
)


def framework(name: str) -> HarnessInfo:
    """Return one certified framework recipe's matrix row (KeyError if unknown)."""
    return FRAMEWORKS[name]


def range_for(harness: str) -> HarnessRange:
    """Return the tested version range for a shipped harness (KeyError if unknown)."""
    return SHIPPED[harness].tested


def render_table() -> str:
    """Render the deterministic compatibility table (sorted by harness id)."""
    lines = [_TABLE_HEADER]
    for harness in sorted(ALL_ROWS):
        info = ALL_ROWS[harness]
        tier = f"{info.tier} (declared)" if info.declared else info.tier
        lines.append(
            f"| `{info.harness}` | {tier} | {info.tested.render()} | "
            f"{info.protocol or '—'} | {info.fidelity} | {info.managed_policy} | "
            f"{info.invocation} | {info.notes} |"
        )
    return "\n".join(lines)


def render_marker_block() -> str:
    """The generated block, including the markers the generator rewrites."""
    return f"{_BEGIN}\n{render_table()}\n{_END}"


# ---------------------------------------------------------------------------
# Version-tagged fixtures + shape fingerprinting
# ---------------------------------------------------------------------------


def _shape(value: Any) -> Any:
    """A value-independent structural view: key names and nested types only."""
    if isinstance(value, Mapping):
        return {key: _shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__


def fixture_fingerprint(fixture: Any) -> str:
    """Stable ``sha256[:16]`` over a fixture's ``message`` shape."""
    message = fixture.get("message") if isinstance(fixture, Mapping) else None
    canonical = json.dumps(_shape(message), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _read_fixture(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def build_baseline(fixtures_root: Path) -> dict[str, Any]:
    """Build the version-tagged fingerprint baseline from the shipped packs."""
    fixtures: dict[str, Any] = {}
    for harness in sorted(SHIPPED):
        directory = fixtures_root / harness
        if not directory.is_dir():
            continue
        version = SHIPPED[harness].tested.maximum
        for path in sorted(directory.glob("*.json")):
            fixture = _read_fixture(path)
            if fixture is None:
                continue
            fixtures[f"{harness}/{path.name}"] = {
                "version": version,
                "fingerprint": fixture_fingerprint(fixture),
            }
    return {"version": 1, "fixtures": fixtures}


def load_baseline(path: Path) -> dict[str, Any]:
    """Read the committed baseline (empty when absent/unreadable)."""
    if not path.exists():
        return {"version": 1, "fixtures": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "fixtures": {}}
    return data if isinstance(data, dict) else {"version": 1, "fixtures": {}}


def detect_drift(fixtures_root: Path, baseline: Mapping[str, Any]) -> list[str]:
    """Return human-readable drift entries (added/removed/shape-changed fixtures)."""
    current = build_baseline(fixtures_root)["fixtures"]
    previous = baseline.get("fixtures")
    previous = previous if isinstance(previous, Mapping) else {}
    drift: list[str] = []
    for key in sorted(set(previous) | set(current)):
        if key not in previous:
            drift.append(f"added fixture: {key}")
        elif key not in current:
            drift.append(f"removed fixture: {key}")
        elif previous[key].get("fingerprint") != current[key]["fingerprint"]:
            drift.append(f"shape changed: {key}")
    return drift


def replace_marker_block(text: str) -> str:
    """Replace (or append) the generated block inside ``text``."""
    block = render_marker_block()
    if _BEGIN in text and _END in text:
        start = text.index(_BEGIN)
        end = text.index(_END) + len(_END)
        return text[:start] + block + text[end:]
    return text.rstrip("\n") + "\n\n" + block + "\n"
