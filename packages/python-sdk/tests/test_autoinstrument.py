"""``agentwatch.instrument()`` auto-detect (M29 FWK-2, PRD 51 §FWK-2, #447).

One call detects installed supported frameworks, wires their telemetry to the local
collector, sets identity from the environment, and reports **what it instrumented
and what it could not** — there is no silent partial instrumentation. It is no-op
safe when agentwatch is not running, registers flush-on-exit, and is idempotent.

The frameworks are not installed here, so detection/wiring are driven through the
injectable seams (``find_spec``, ``is_running``, ``wire``, ``register_exit``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping

import pytest

import agentwatch
from agentwatch import autoinstrument
from agentwatch.frameworks import RECIPES, FrameworkRecipe


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    autoinstrument.reset()
    yield
    autoinstrument.reset()


def _find_spec(*modules: str) -> Callable[[str], object | None]:
    present = set(modules)

    def probe(module: str) -> object | None:
        return object() if module in present else None

    return probe


def _all_modules() -> list[str]:
    return [recipe.module for recipe in RECIPES.values()]


def test_agentwatch_instrument_is_callable_and_keeps_the_module() -> None:
    assert callable(agentwatch.instrument)
    from agentwatch.instrument import invoke_agent  # noqa: PLC0415 - back-compat check

    assert callable(invoke_agent)


def test_noop_safe_when_agentwatch_is_not_running() -> None:
    report = autoinstrument.instrument(
        find_spec=_find_spec("google.adk"),
        is_running=lambda: False,
        print_report=False,
    )

    assert report.noop is True
    assert report.detected == ("adk",)
    assert report.instrumented == ()
    assert [gap.framework for gap in report.gaps] == ["adk"]
    assert "not running" in report.gaps[0].reason


def test_instruments_detected_frameworks_and_wires_the_collector() -> None:
    wired: list[str] = []
    report = autoinstrument.instrument(
        find_spec=_find_spec(*_all_modules()),
        is_running=lambda: True,
        wire=lambda recipe, endpoint, env: wired.append(recipe.name),
        register_exit=lambda fn: None,
        print_report=False,
    )

    assert report.noop is False
    assert set(report.instrumented) == set(RECIPES)
    assert report.gaps == ()
    assert sorted(wired) == sorted(RECIPES)
    assert report.endpoint


def test_a_wiring_failure_is_reported_not_silently_dropped() -> None:
    def wire(
        recipe: FrameworkRecipe, endpoint: str, env: MutableMapping[str, str]
    ) -> None:
        if recipe.name == "strands":
            raise RuntimeError("instrumentor exploded")

    report = autoinstrument.instrument(
        find_spec=_find_spec(*_all_modules()),
        is_running=lambda: True,
        wire=wire,
        register_exit=lambda fn: None,
        print_report=False,
    )

    assert "strands" not in report.instrumented
    assert "adk" in report.instrumented
    gaps = {gap.framework: gap.reason for gap in report.gaps}
    assert "strands" in gaps and "exploded" in gaps["strands"]


def test_an_unsupported_framework_is_an_explicit_gap() -> None:
    report = autoinstrument.instrument(
        include=("adk", "some-unknown-framework"),
        find_spec=_find_spec("google.adk"),
        is_running=lambda: True,
        wire=lambda recipe, endpoint, env: None,
        register_exit=lambda fn: None,
        print_report=False,
    )

    gaps = {gap.framework: gap.reason for gap in report.gaps}
    assert "no certified recipe" in gaps["some-unknown-framework"]
    assert "adk" in report.instrumented


def test_second_call_is_idempotent_and_does_not_rewire() -> None:
    wired: list[str] = []

    def _instrument() -> autoinstrument.InstrumentReport:
        return autoinstrument.instrument(
            find_spec=_find_spec("google.adk"),
            is_running=lambda: True,
            wire=lambda recipe, endpoint, env: wired.append(recipe.name),
            register_exit=lambda fn: None,
            print_report=False,
        )

    first = _instrument()
    second = _instrument()

    assert first.instrumented == ("adk",)
    assert second.instrumented == ()
    assert second.already == ("adk",)
    assert wired == ["adk"]


def test_flush_on_exit_is_registered_once() -> None:
    registered: list[object] = []

    def _instrument() -> autoinstrument.InstrumentReport:
        return autoinstrument.instrument(
            find_spec=_find_spec("google.adk"),
            is_running=lambda: True,
            wire=lambda recipe, endpoint, env: None,
            register_exit=registered.append,
            print_report=False,
        )

    _instrument()
    _instrument()
    # round 1 registers after first call; round 2 finds everything already done and
    # does not need to register again.
    assert len(registered) == 1
    assert callable(registered[0])


def test_identity_is_taken_from_the_environment() -> None:
    report = autoinstrument.instrument(
        find_spec=_find_spec("google.adk"),
        is_running=lambda: True,
        wire=lambda recipe, endpoint, env: None,
        register_exit=lambda fn: None,
        env={"AGENTWATCH_AGENT_NAME": "triage", "OTEL_SERVICE_NAME": "svc"},
        print_report=False,
    )

    assert report.identity["agent_name"] == "triage"
    assert report.identity["service_name"] == "svc"


def test_it_prints_detected_frameworks_and_gaps(
    capsys: pytest.CaptureFixture[str],
) -> None:
    autoinstrument.instrument(
        find_spec=_find_spec("google.adk"),
        is_running=lambda: False,
        print_report=True,
    )

    out = capsys.readouterr().out
    assert "detected" in out
    assert "adk" in out
    assert "gap" in out


def test_default_running_probe_is_false_when_nothing_listens() -> None:
    env = {"AGENTWATCH_HEALTH_ENDPOINT": "127.0.0.1:1"}
    assert autoinstrument._default_is_running(env) is False


def test_default_wire_sets_the_otlp_endpoint() -> None:
    env: dict[str, str] = {}
    recipe = RECIPES["adk"]

    autoinstrument._default_wire(recipe, "http://127.0.0.1:4317", env)

    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://127.0.0.1:4317"