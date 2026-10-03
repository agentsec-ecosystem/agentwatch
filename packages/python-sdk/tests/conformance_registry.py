"""Register shipped adapters into the shared conformance runner (M5 O1, #216).

Importing this module registers every shipped adapter exactly once so the
conformance tests can parametrize over them. A shipped adapter that is not
registered fails ``test_all_shipped_adapters_are_registered``.
"""

from __future__ import annotations

from pathlib import Path

from agentwatch import conformance
from agentwatch.adapters import claude_code, codex_cli, cursor

FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def _shipped_specs() -> list[conformance.AdapterSpec]:
    return [claude_code_spec(), cursor_spec(), codex_cli_spec()]


def register_shipped_adapters() -> None:
    for spec in _shipped_specs():
        if spec.name not in conformance.registered_names():
            conformance.register(spec)


register_shipped_adapters()
