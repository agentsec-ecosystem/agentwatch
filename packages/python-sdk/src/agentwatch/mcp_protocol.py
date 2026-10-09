"""MCP protocol-revision conformance matrix (M27 MCP-6, #338).

The MCP specification revised under us — ``2025-06-18`` → ``2025-11-25`` →
``2026-07-28`` — adding elicitation, resource links, experimental then redesigned
tasks, and (in 2026-07-28) removing sessions and retiring Roots/Sampling/Logging.
This module is the single source of truth for which surfaces are recorded at each
revision, so protocol drift (a new revision, or the proxy's tested range lagging
the matrix) fails CI instead of surprising a user.
"""

from __future__ import annotations

# Oldest → newest; the tested compatibility range must not lag the newest.
PROTOCOL_VERSIONS: tuple[str, ...] = ("2025-06-18", "2025-11-25", "2026-07-28")

LATEST_PROTOCOL_VERSION = PROTOCOL_VERSIONS[-1]

# Surface capability ids recorded per revision. Elicitation + resource links
# arrived in 2025-06-18; experimental tasks in 2025-11-25; the 2026-07-28
# revision redesigns tasks (SEP-2663) and removes sessions (SEP-2567).
SURFACES_BY_REVISION: dict[str, tuple[str, ...]] = {
    "2025-06-18": ("mcp-tools", "mcp-resources", "mcp-prompts", "mcp-elicitation"),
    "2025-11-25": (
        "mcp-tools",
        "mcp-resources",
        "mcp-prompts",
        "mcp-elicitation",
        "mcp-tasks",
    ),
    "2026-07-28": (
        "mcp-tools",
        "mcp-resources",
        "mcp-prompts",
        "mcp-elicitation",
        "mcp-tasks",
    ),
}

# Surfaces the 2026-07-28 revision retired (SEP-2577): relayed, never recorded.
CLOSED_BY_SPEC: frozenset[str] = frozenset({"roots", "sampling", "logging"})


def supported_surfaces(revision: str) -> frozenset[str]:
    """The recorded surface capability ids for one protocol revision."""
    return frozenset(SURFACES_BY_REVISION[revision])


def protocol_matrix() -> list[tuple[str, tuple[str, ...]]]:
    """``(revision, surfaces)`` rows in version order (for docs/tests)."""
    return [(revision, SURFACES_BY_REVISION[revision]) for revision in PROTOCOL_VERSIONS]


__all__ = [
    "CLOSED_BY_SPEC",
    "LATEST_PROTOCOL_VERSION",
    "PROTOCOL_VERSIONS",
    "SURFACES_BY_REVISION",
    "protocol_matrix",
    "supported_surfaces",
]
