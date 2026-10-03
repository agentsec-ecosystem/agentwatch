"""Register shipped adapters into the shared conformance runner (M5 O1, #216).

Importing this module registers every shipped adapter exactly once so the
conformance tests can parametrize over them. A shipped adapter that is not
registered fails ``test_all_shipped_adapters_are_registered``.
"""

from __future__ import annotations

from pathlib import Path

from agentwatch import conformance
from agentwatch.adapters import claude_code

CLAUDE_CODE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude-code"


def claude_code_spec() -> conformance.AdapterSpec:
    return conformance.AdapterSpec(
        name=claude_code.HARNESS_ID,
        normalize=claude_code.normalize,
        capabilities=claude_code.CAPABILITIES,
        documented_gaps=claude_code.DOCUMENTED_GAPS,
        error_cls=claude_code.ClaudeCodeAdapterError,
        fixtures_dir=CLAUDE_CODE_FIXTURES,
    )


def register_shipped_adapters() -> None:
    spec = claude_code_spec()
    if spec.name not in conformance.registered_names():
        conformance.register(spec)


register_shipped_adapters()
