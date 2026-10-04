"""Shared adapter conformance runner (M5 O1, #216).

Every adapter registers an :class:`AdapterSpec` and must pass the same bar,
mechanically, in CI: fixture replay, capability/gap disjointness, explicit
rejection of declared gaps and unknown phases, record validation on every
output, and dedup/idempotency. The runner is the plugin contract community
adapters build against (J1) — a failure blocks merge.

Usage::

    from agentwatch import conformance

    conformance.register(my_spec)
    conformance.assert_registered_conform()
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentwatch.records import AgentRecord, validate_record

# Checks emitted by the runner; each failure is prefixed with one of these.
CHECK_REGISTRATION = "registration"
CHECK_DISJOINTNESS = "capability-gap-disjointness"
CHECK_FIXTURES = "fixtures-populated"
CHECK_REPLAY = "fixture-replay"
CHECK_GAP_REJECTION = "declared-gap-rejection"
CHECK_UNKNOWN_REJECTION = "unknown-phase-rejection"
CHECK_DEDUP = "dedup-idempotency"


@dataclass(frozen=True)
class AdapterSpec:
    """Everything the runner needs to hold one adapter to the contract."""

    name: str
    normalize: Callable[[Mapping[str, Any]], list[AgentRecord]]
    capabilities: frozenset[str]
    documented_gaps: tuple[str, ...]
    error_cls: type[Exception]
    fixtures_dir: Path
    probe: Callable[[str], Mapping[str, Any]] | None = None


@dataclass
class ConformanceReport:
    """Result of running the contract against one adapter."""

    adapter: str
    failures: list[str] = field(default_factory=list)
    checks: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        lines = [
            f"{self.adapter}: {len(self.failures)} conformance failure(s) "
            f"across {self.checks} check(s)"
        ]
        lines.extend(f"  - {failure}" for failure in self.failures)
        return "\n".join(lines)


class ConformanceError(AssertionError):
    """Raised when an adapter does not meet the conformance contract."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, AdapterSpec] = {}


def register(spec: AdapterSpec, *, replace: bool = False) -> None:
    """Register an adapter; a duplicate name fails closed unless ``replace``."""
    if spec.name in _REGISTRY and not replace:
        raise ValueError(f"adapter {spec.name!r} is already registered")
    _REGISTRY[spec.name] = spec


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)


def registered() -> list[AdapterSpec]:
    """Every registered adapter, deterministically ordered."""
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def registered_names() -> list[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _default_probe(phase: str) -> Mapping[str, Any]:
    return {"phase": phase, "event": {"session_id": "conformance"}}


def _load_fixtures(directory: Path) -> tuple[list[tuple[Path, Any]], list[str]]:
    if not directory.is_dir():
        return [], [f"{CHECK_FIXTURES}: fixtures directory {directory} does not exist"]
    paths = sorted(directory.glob("*.json"))
    if not paths:
        return [], [f"{CHECK_FIXTURES}: no *.json fixtures in {directory}"]
    loaded: list[tuple[Path, Any]] = []
    failures: list[str] = []
    for path in paths:
        try:
            loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            failures.append(f"{CHECK_REPLAY}: {path.name} is not readable JSON: {exc}")
    return loaded, failures


def _record_dicts(records: Any) -> list[dict[str, Any]]:
    """Dump adapter output to plain dicts, validating every record (F8)."""
    if not isinstance(records, list):
        raise TypeError(f"normalize returned {type(records).__name__}, expected list")
    dumped: list[dict[str, Any]] = []
    for record in records:
        to_dict = getattr(record, "to_dict", None)
        if to_dict is None:
            raise TypeError(f"normalize output {record!r} is not an AgentRecord")
        data = to_dict()
        validate_record(data)
        dumped.append(data)
    return dumped


def _check_registration(spec: AdapterSpec, report: ConformanceReport) -> None:
    report.checks += 1
    if not spec.name:
        report.failures.append(f"{CHECK_REGISTRATION}: adapter name must not be empty")


def _check_disjointness(spec: AdapterSpec, report: ConformanceReport) -> None:
    report.checks += 1
    if not spec.capabilities:
        report.failures.append(
            f"{CHECK_DISJOINTNESS}: adapter must declare at least one capability"
        )
    overlap = set(spec.documented_gaps) & set(spec.capabilities)
    if overlap:
        report.failures.append(
            f"{CHECK_DISJOINTNESS}: classes both claimed and declared as gaps: "
            f"{', '.join(sorted(overlap))}"
        )
    if len(set(spec.documented_gaps)) != len(spec.documented_gaps):
        report.failures.append(f"{CHECK_DISJOINTNESS}: duplicate documented gaps")


def _check_rejection(spec: AdapterSpec, report: ConformanceReport, phase: str, check: str) -> None:
    probe = spec.probe or _default_probe
    try:
        spec.normalize(probe(phase))
    except spec.error_cls:
        return
    except Exception as exc:  # noqa: BLE001 - wrong error type is still a failure
        report.failures.append(
            f"{check}: phase {phase!r} raised {type(exc).__name__}, expected "
            f"{spec.error_cls.__name__}"
        )
        return
    report.failures.append(
        f"{check}: phase {phase!r} was accepted or dropped silently; expected "
        f"{spec.error_cls.__name__}"
    )


def _check_fixture_replay(
    spec: AdapterSpec, report: ConformanceReport, loaded: list[tuple[Path, Any]]
) -> None:
    for path, fixture in loaded:
        if not isinstance(fixture, dict) or "message" not in fixture or "expected" not in fixture:
            report.failures.append(
                f"{CHECK_REPLAY}: {path.name} must define 'message' and 'expected'"
            )
            continue
        message = fixture["message"]
        before = copy.deepcopy(message)
        try:
            records = spec.normalize(message)
            dumped = _record_dicts(records)
        except (TypeError, ValueError, KeyError) as exc:
            report.failures.append(f"{CHECK_REPLAY}: {path.name}: {exc}")
            continue
        if message != before:
            report.failures.append(f"{CHECK_REPLAY}: {path.name}: normalize mutated its input")
        if dumped != fixture["expected"]:
            report.failures.append(f"{CHECK_REPLAY}: {path.name}: output != expected")


def _check_dedup(
    spec: AdapterSpec, report: ConformanceReport, loaded: list[tuple[Path, Any]]
) -> None:
    for path, fixture in loaded:
        if not isinstance(fixture, dict) or "message" not in fixture:
            continue
        message = fixture["message"]
        try:
            first = _record_dicts(spec.normalize(copy.deepcopy(message)))
            second = _record_dicts(spec.normalize(copy.deepcopy(message)))
        except (TypeError, ValueError, KeyError) as exc:
            report.failures.append(f"{CHECK_DEDUP}: {path.name}: {exc}")
            continue
        if first != second:
            report.failures.append(
                f"{CHECK_DEDUP}: {path.name}: normalizing twice is not idempotent"
            )


def run(spec: AdapterSpec) -> ConformanceReport:
    """Run every contract check against one adapter; never raises for a failure."""
    report = ConformanceReport(adapter=spec.name)
    _check_registration(spec, report)
    _check_disjointness(spec, report)

    loaded, load_failures = _load_fixtures(spec.fixtures_dir)
    report.checks += 1
    report.failures.extend(load_failures)
    if loaded:
        _check_fixture_replay(spec, report, loaded)
        _check_dedup(spec, report, loaded)
    report.checks += 2

    if spec.documented_gaps:
        for gap in spec.documented_gaps:
            _check_rejection(spec, report, gap, CHECK_GAP_REJECTION)
    else:
        report.failures.append(
            f"{CHECK_GAP_REJECTION}: adapter declares no documented gaps to prove rejection"
        )
    report.checks += 1

    _check_rejection(spec, report, "__unsupported-conformance-phase__", CHECK_UNKNOWN_REJECTION)
    report.checks += 1
    return report


def assert_conforms(spec: AdapterSpec) -> None:
    """Raise :class:`ConformanceError` unless the adapter meets the contract."""
    report = run(spec)
    if not report.ok:
        raise ConformanceError(report.summary())


def run_registered() -> list[ConformanceReport]:
    return [run(spec) for spec in registered()]


def assert_registered_conform() -> None:
    """Block CI when no adapter is registered or any registered adapter fails."""
    specs = registered()
    if not specs:
        raise ConformanceError("no adapters registered for conformance")
    failed = [report for report in (run(spec) for spec in specs) if not report.ok]
    if failed:
        raise ConformanceError("\n".join(report.summary() for report in failed))


def assert_packs_populated() -> None:
    """Block CI when a registered adapter lacks a well-formed conformance pack.

    A harness may claim "supported" only with a populated fixtures directory
    whose cases define ``message`` and ``expected`` (M10 #85).
    """
    problems: list[str] = []
    for spec in registered():
        paths = sorted(spec.fixtures_dir.glob("*.json")) if spec.fixtures_dir.is_dir() else []
        if not paths:
            problems.append(f"{spec.name}: no conformance fixtures in {spec.fixtures_dir}")
            continue
        for path in paths:
            try:
                fixture = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(f"{spec.name}: {path.name} is not readable JSON: {exc}")
                continue
            if not isinstance(fixture, dict) or not {"message", "expected"} <= set(fixture):
                problems.append(f"{spec.name}: {path.name} must define 'message' and 'expected'")
    if problems:
        raise ConformanceError("\n".join(problems))
