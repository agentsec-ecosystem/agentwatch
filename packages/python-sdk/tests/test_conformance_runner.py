"""Shared adapter conformance runner (M5 O1, #216).

The runner is the reusable contract every registered adapter must pass:
fixture replay, capability/gap disjointness, explicit rejection of declared
gaps and unknown phases, record validation on every output, and
dedup/idempotency. A deliberately-broken sample adapter proves the gate works.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import conformance_registry  # noqa: F401  (registers shipped adapters)
import pytest

from agentwatch import adapters, conformance
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    StepType,
    ToolCall,
    _parse_iso,
)

FIXTURE = {
    "message": {
        "phase": "pre",
        "harness": "synthetic",
        "event": {
            "session_id": "s-1",
            "tool_name": "Bash",
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    },
    "expected": [
        {
            "schema_version": "0.1.0",
            "session_id": "s-1",
            "agent": {"identity": "unknown"},
            "tool": {"name": "Bash"},
            "outcome": "ok",
            "started_at": "2026-01-02T03:04:05+00:00",
            "harness": "synthetic",
            "trace_id": "s-1",
            "step_type": "act",
        }
    ],
}


def _write_fixture(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pre.json").write_text(json.dumps(FIXTURE), encoding="utf-8")


def _normalize_pre(message: Mapping[str, Any]) -> list[AgentRecord]:
    return [
        AgentRecord(
            session_id="s-1",
            agent=AgentIdentity(identity="unknown"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=_parse_iso("2026-01-02T03:04:05+00:00"),
            harness="synthetic",
            trace_id="s-1",
            step_type=StepType.ACT,
        )
    ]


def _good_spec(tmp_path: Path) -> conformance.AdapterSpec:
    _write_fixture(tmp_path / "fixtures")
    return conformance.AdapterSpec(
        name="synthetic-good",
        normalize=_always_rejects,
        capabilities=frozenset({"pre-tool-use"}),
        documented_gaps=("mcp-server-events",),
        error_cls=ValueError,
        fixtures_dir=tmp_path / "fixtures",
    )


def _always_rejects(message: Mapping[str, Any]) -> list[AgentRecord]:
    phase = message.get("phase")
    if phase == "pre":
        return _normalize_pre(message)
    raise ValueError(f"unsupported phase {phase!r}")


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conformance, "_REGISTRY", {})


# -- registry --------------------------------------------------------------


def test_claude_code_is_registered_by_the_registry_module() -> None:
    assert "claude-code" in conformance.registered_names()


def test_all_shipped_adapters_are_registered() -> None:
    for module_name in adapters.__all__:
        module = importlib.import_module(f"agentwatch.adapters.{module_name}")
        harness_id = module.HARNESS_ID
        assert harness_id in conformance.registered_names(), (
            f"{module_name} is shipped but not registered for conformance"
        )


def test_registering_a_duplicate_is_rejected(clean_registry: None, tmp_path: Path) -> None:
    spec = _good_spec(tmp_path)
    conformance.register(spec)
    with pytest.raises(ValueError):
        conformance.register(spec)
    conformance.register(spec, replace=True)


def test_no_registered_adapter_fails_closed(clean_registry: None) -> None:
    with pytest.raises(conformance.ConformanceError):
        conformance.assert_registered_conform()


# -- a conformant adapter --------------------------------------------------


def test_conformant_adapter_passes(tmp_path: Path) -> None:
    report = conformance.run(_good_spec(tmp_path))
    assert report.ok, report.summary()
    assert report.checks >= 5


def test_assert_conforms_is_silent_for_a_conformant_adapter(tmp_path: Path) -> None:
    conformance.assert_conforms(_good_spec(tmp_path))


def test_registered_shipped_adapters_conform() -> None:
    reports = conformance.run_registered()
    assert reports
    for report in reports:
        assert report.ok, report.summary()


def test_assert_registered_conform_raises_on_a_broken_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = _broken_spec(tmp_path)
    monkeypatch.setattr(conformance, "_REGISTRY", {spec.name: spec})
    with pytest.raises(conformance.ConformanceError):
        conformance.assert_registered_conform()


# -- the deliberately-broken sample adapter --------------------------------


class _BrokenAdapter:
    """Claims support and declares the same class as a gap, then drops it."""

    name = "broken"
    capabilities = frozenset({"pre-tool-use"})
    documented_gaps = ("pre-tool-use",)
    error_cls: type[Exception] = ValueError

    def normalize(self, message: Mapping[str, Any]) -> list[AgentRecord]:
        return []  # silently drops everything, including declared gaps


def _broken_spec(tmp_path: Path) -> conformance.AdapterSpec:
    _write_fixture(tmp_path / "fixtures")
    adapter = _BrokenAdapter()
    return conformance.AdapterSpec(
        name=adapter.name,
        normalize=adapter.normalize,
        capabilities=adapter.capabilities,
        documented_gaps=adapter.documented_gaps,
        error_cls=adapter.error_cls,
        fixtures_dir=tmp_path / "fixtures",
    )


def test_runner_fails_a_broken_adapter(tmp_path: Path) -> None:
    report = conformance.run(_broken_spec(tmp_path))
    assert not report.ok
    prefixes = {failure.split(":", 1)[0] for failure in report.failures}
    assert "capability-gap-disjointness" in prefixes
    assert "declared-gap-rejection" in prefixes
    assert "unknown-phase-rejection" in prefixes
    assert "fixture-replay" in prefixes


def test_assert_conforms_raises_for_a_broken_adapter(tmp_path: Path) -> None:
    with pytest.raises(conformance.ConformanceError) as exc:
        conformance.assert_conforms(_broken_spec(tmp_path))
    assert "broken" in str(exc.value)


def test_runner_rejects_invalid_record_outputs(tmp_path: Path) -> None:
    _write_fixture(tmp_path / "fixtures")

    def bad_normalize(message: Mapping[str, Any]) -> list[AgentRecord]:
        return [{"not": "a record"}]  # type: ignore[list-item]

    spec = conformance.AdapterSpec(
        name="bad-records",
        normalize=bad_normalize,
        capabilities=frozenset({"pre-tool-use"}),
        documented_gaps=("mcp-server-events",),
        error_cls=ValueError,
        fixtures_dir=tmp_path / "fixtures",
    )

    report = conformance.run(spec)
    assert not report.ok
    assert any(failure.startswith("fixture-replay") for failure in report.failures)


def test_runner_rejects_an_empty_adapter_name(tmp_path: Path) -> None:
    _write_fixture(tmp_path / "fixtures")
    spec = conformance.AdapterSpec(
        name="",
        normalize=_always_rejects,
        capabilities=frozenset({"pre"}),
        documented_gaps=("gap",),
        error_cls=ValueError,
        fixtures_dir=tmp_path / "fixtures",
    )
    report = conformance.run(spec)
    assert any(failure.startswith("registration") for failure in report.failures)


def test_self_test_proves_a_broken_adapter_fails() -> None:
    # XHT-1 negative control: a deliberately broken adapter must fail the runner.
    assert conformance.self_test() is True
