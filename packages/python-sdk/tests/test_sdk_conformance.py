"""SDK conformance pack CI gate (M27 LG-1, O1).

Registers the LangGraph SDK pack and holds it — and the SDK runner — to the same
mechanical bar as the adapter packs: fixture replay, record validation, and
idempotency, with a negative control proving a broken pack fails.
"""

from __future__ import annotations

import sdk_conformance_registry  # noqa: F401  (registers the packs)

from agentwatch import conformance


def test_langgraph_sdk_pack_conforms() -> None:
    conformance.assert_sdk_conform()


def test_sdk_pack_is_registered() -> None:
    assert "langgraph" in {spec.name for spec in conformance.registered_sdks()}


def test_sdk_runner_fails_a_broken_pack() -> None:
    broken = conformance.SdkSpec(
        name="__broken__",
        replay=lambda _input: [],
        fixtures_dir=sdk_conformance_registry.FIXTURES,
        error_cls=ValueError,
    )

    report = conformance.run_sdk(broken)

    assert not report.ok
    assert any("sdk-fixture-replay" in failure for failure in report.failures)
