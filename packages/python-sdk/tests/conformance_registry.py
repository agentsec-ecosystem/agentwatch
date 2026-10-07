"""Register shipped adapters into the shared conformance runner (M5 O1, #216).

Importing this module registers every shipped adapter exactly once so the
conformance tests can parametrize over them. A shipped adapter that is not
registered fails ``test_all_shipped_adapters_are_registered``.
"""

from __future__ import annotations

from pathlib import Path

from agentwatch import conformance
from agentwatch.adapters import (
    a2a_proxy,
    claude_code,
    codex_cli,
    crewai,
    cursor,
    gemini_cli,
    mcp_proxy,
    pydantic_ai,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def a2a_proxy_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=a2a_proxy.HARNESS_ID,
        normalize=a2a_proxy.normalize,
        capabilities=a2a_proxy.CAPABILITIES,
        documented_gaps=a2a_proxy.DOCUMENTED_GAPS,
        error_cls=a2a_proxy.A2aProxyAdapterError,
        fixtures_dir=FIXTURES / "a2a-proxy",
    )


def claude_code_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=claude_code.HARNESS_ID,
        normalize=claude_code.normalize,
        capabilities=claude_code.CAPABILITIES,
        documented_gaps=claude_code.DOCUMENTED_GAPS,
        error_cls=claude_code.ClaudeCodeAdapterError,
        fixtures_dir=FIXTURES / "claude-code",
    )


def cursor_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=cursor.HARNESS_ID,
        normalize=cursor.normalize,
        capabilities=cursor.CAPABILITIES,
        documented_gaps=cursor.DOCUMENTED_GAPS,
        error_cls=cursor.CursorAdapterError,
        fixtures_dir=FIXTURES / "cursor",
    )


def codex_cli_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=codex_cli.HARNESS_ID,
        normalize=codex_cli.normalize,
        capabilities=codex_cli.CAPABILITIES,
        documented_gaps=codex_cli.DOCUMENTED_GAPS,
        error_cls=codex_cli.CodexCliAdapterError,
        fixtures_dir=FIXTURES / "codex-cli",
    )


def gemini_cli_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=gemini_cli.HARNESS_ID,
        normalize=gemini_cli.normalize,
        capabilities=gemini_cli.CAPABILITIES,
        documented_gaps=gemini_cli.DOCUMENTED_GAPS,
        error_cls=gemini_cli.GeminiCliAdapterError,
        fixtures_dir=FIXTURES / "gemini-cli",
    )


def mcp_proxy_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=mcp_proxy.HARNESS_ID,
        normalize=mcp_proxy.normalize,
        capabilities=mcp_proxy.CAPABILITIES,
        documented_gaps=mcp_proxy.DOCUMENTED_GAPS,
        error_cls=mcp_proxy.McpProxyAdapterError,
        fixtures_dir=FIXTURES / "mcp-proxy",
    )


def crewai_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=crewai.HARNESS_ID,
        normalize=crewai.normalize,
        capabilities=crewai.CAPABILITIES,
        documented_gaps=crewai.DOCUMENTED_GAPS,
        error_cls=crewai.CrewAiAdapterError,
        fixtures_dir=FIXTURES / "crewai",
    )


def pydantic_ai_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=pydantic_ai.HARNESS_ID,
        normalize=pydantic_ai.normalize,
        capabilities=pydantic_ai.CAPABILITIES,
        documented_gaps=pydantic_ai.DOCUMENTED_GAPS,
        error_cls=pydantic_ai.PydanticAiAdapterError,
        fixtures_dir=FIXTURES / "pydantic-ai",
    )


def _shipped_specs() -> list[conformance.AdapterSpec]:
    return [
        claude_code_spec(),
        cursor_spec(),
        codex_cli_spec(),
        gemini_cli_spec(),
        mcp_proxy_spec(),
        a2a_proxy_spec(),
        crewai_spec(),
        pydantic_ai_spec(),
    ]


def register_shipped_adapters() -> None:
    for spec in _shipped_specs():
        if spec.name not in conformance.registered_names():
            conformance.register(spec)


register_shipped_adapters()
