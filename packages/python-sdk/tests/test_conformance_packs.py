"""Per-harness conformance pack manifest (M10 #85).

Every registered adapter must ship a populated, well-formed conformance pack so
"supported" cannot be claimed without one.
"""

from __future__ import annotations

import json

import conformance_registry  # noqa: F401  (registers shipped adapters)
import pytest

from agentwatch import conformance


def test_registered_adapters_have_populated_packs() -> None:
    conformance.assert_packs_populated()


@pytest.mark.parametrize("spec", conformance.registered(), ids=lambda spec: spec.name)
def test_each_pack_case_defines_message_and_expected(spec: conformance.AdapterSpec) -> None:
    paths = sorted(spec.fixtures_dir.glob("*.json"))

    assert paths, f"{spec.name} has no conformance fixtures"
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        assert {"message", "expected"} <= set(fixture), path.name
