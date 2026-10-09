"""``agentwatch.instrument()`` auto-detect (M29 FWK-2, PRD 51 §FWK-2, #447).

One call detects the installed supported frameworks, wires their OpenTelemetry to
the local collector, takes identity from the environment, and reports **what it
instrumented and what it could not**. The contract:

* **No silent partial instrumentation.** Every detected framework either appears in
  ``instrumented`` or in ``gaps`` with a reason.
* **No-op safe.** When agentwatch is not running the call wires nothing and says so.
* **Flush-on-exit.** A single ``atexit`` hook flushes the active OTel provider.
* **Idempotent.** A second call does not re-wire a framework (no double spans).

There is no new runtime dependency: detection uses ``importlib.util.find_spec`` and
wiring uses the standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` (plus the OpenInference
instrumentor for the OpenAI Agents SDK). ``agentwatch.instrument`` is the callable
entry point; this module holds the implementation.
"""

from __future__ import annotations

import atexit
import importlib.util
import os
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urlsplit

from agentwatch import frameworks

# The local collector's OTLP endpoint used when the environment does not name one.
DEFAULT_OTLP_ENDPOINT = "http://127.0.0.1:4317"
# The local recorder health endpoint probed to decide if agentwatch is running.
HEALTH_ENDPOINT_ENV = "AGENTWATCH_HEALTH_ENDPOINT"
DEFAULT_HEALTH_ENDPOINT = "127.0.0.1:9100"

# Frameworks already wired in this process (idempotence / no double spans).
_INSTRUMENTED: set[str] = set()
_EXIT_REGISTERED = False


@dataclass(frozen=True)
class InstrumentGap:
    """A detected (or requested) framework agentwatch could not instrument."""

    framework: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"framework": self.framework, "reason": self.reason}


@dataclass(frozen=True)
class InstrumentReport:
    """What ``agentwatch.instrument()`` detected, wired, and could not wire."""

    detected: tuple[str, ...] = ()
    instrumented: tuple[str, ...] = ()
    gaps: tuple[InstrumentGap, ...] = ()
    not_detected: tuple[str, ...] = ()
    already: tuple[str, ...] = ()
    noop: bool = False
    endpoint: str | None = None
    identity: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": list(self.detected),
            "instrumented": list(self.instrumented),
            "gaps": [gap.to_dict() for gap in self.gaps],
            "not_detected": list(self.not_detected),
            "already": list(self.already),
            "noop": self.noop,
            "endpoint": self.endpoint,
            "identity": dict(self.identity),
        }

    def summary(self) -> str:
        lines: list[str] = []
        if self.noop:
            lines.append("agentwatch.instrument: no-op (recorder not running)")
        else:
            lines.append(
                f"agentwatch.instrument: instrumented {len(self.instrumented)} framework(s)"
            )
        lines.append(f"  detected: {', '.join(self.detected) or '(none)'}")
        lines.append(f"  instrumented: {', '.join(self.instrumented) or '(none)'}")
        lines.append(f"  already: {', '.join(self.already) or '(none)'}")
        lines.append(f"  not detected: {', '.join(self.not_detected) or '(none)'}")
        if self.gaps:
            lines.append("  gaps:")
            lines.extend(f"    - {gap.framework}: {gap.reason}" for gap in self.gaps)
        else:
            lines.append("  gaps: (none)")
        return "\n".join(lines)


def reset() -> None:
    """Forget what has been instrumented (test isolation / reconfigure)."""
    global _EXIT_REGISTERED
    _INSTRUMENTED.clear()
    _EXIT_REGISTERED = False


def identity_from_env(env: Mapping[str, str]) -> dict[str, str]:
    """Read run identity from the environment (never inventing a value)."""
    identity: dict[str, str] = {}
    if env.get("AGENTWATCH_AGENT_NAME"):
        identity["agent_name"] = env["AGENTWATCH_AGENT_NAME"]
    if env.get("AGENTWATCH_AGENT_VERSION"):
        identity["agent_version"] = env["AGENTWATCH_AGENT_VERSION"]
    if env.get("OTEL_SERVICE_NAME"):
        identity["service_name"] = env["OTEL_SERVICE_NAME"]
    return identity


def _endpoint_from_env(env: Mapping[str, str]) -> str:
    return (
        env.get("AGENTWATCH_OTLP_ENDPOINT")
        or env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or DEFAULT_OTLP_ENDPOINT
    )


def _health_url(endpoint: str) -> str:
    if "://" not in endpoint:
        endpoint = f"http://{endpoint}"
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}/healthz"


def _default_is_running(env: Mapping[str, str]) -> bool:
    """Probe the local recorder health endpoint; any failure means "not running"."""
    import urllib.error
    import urllib.request

    endpoint = env.get(HEALTH_ENDPOINT_ENV, DEFAULT_HEALTH_ENDPOINT)
    try:
        with urllib.request.urlopen(_health_url(endpoint), timeout=0.5) as response:  # noqa: S310
            return bool(200 <= response.status < 300)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _default_wire(
    recipe: frameworks.FrameworkRecipe,
    endpoint: str,
    env: MutableMapping[str, str],
) -> None:
    """Point a framework's OTel exporter at the local collector.

    Every recipe honors ``OTEL_EXPORTER_OTLP_ENDPOINT``. The OpenAI Agents SDK also
    needs its OpenInference instrumentor activated; if that is unavailable the call
    raises and the framework is reported as a gap (never a silent partial).
    """
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    if recipe.name == "openai-agents":
        module = importlib.import_module("openinference.instrumentation.openai_agents")
        instrumentor = cast("Any", module).OpenAIAgentsInstrumentor
        instrumentor().instrument()


def flush_active_provider() -> bool:
    """ForceFlush the active OTel provider on exit (OTel ForceFlush semantic)."""
    try:
        from opentelemetry import trace  # noqa: PLC0415

        provider = trace.get_tracer_provider()
        force_flush = getattr(provider, "force_flush", None)
        if callable(force_flush):
            return bool(force_flush())
    except Exception:  # noqa: BLE001 - exit must never raise
        return False
    return False


def _normalize_include(include: Iterable[str] | None) -> list[str]:
    if include is None:
        return list(frameworks.SUPPORTED_FRAMEWORKS)
    seen: list[str] = []
    for name in include:
        if name not in seen:
            seen.append(name)
    return seen


def instrument(
    *,
    include: Iterable[str] | None = None,
    identity: Mapping[str, str] | None = None,
    endpoint: str | None = None,
    is_running: Callable[[], bool] | None = None,
    find_spec: Callable[[str], object] | None = None,
    env: MutableMapping[str, str] | None = None,
    wire: Callable[[frameworks.FrameworkRecipe, str, MutableMapping[str, str]], None] | None = None,
    register_exit: Callable[[Callable[[], object]], object] | None = None,
    print_report: bool = True,
) -> InstrumentReport:
    """Detect, wire, and report framework telemetry in one call (FWK-2)."""
    global _EXIT_REGISTERED

    environ: MutableMapping[str, str] = os.environ if env is None else env
    probe = find_spec or importlib.util.find_spec
    running = is_running() if is_running is not None else _default_is_running(environ)
    target_endpoint = endpoint or _endpoint_from_env(environ)
    report_identity = dict(identity) if identity is not None else identity_from_env(environ)

    requested = _normalize_include(include)
    supported = [name for name in requested if name in frameworks.RECIPES]
    unsupported = [name for name in requested if name not in frameworks.RECIPES]

    detection = frameworks.detect_installed(find_spec=probe)
    installed = set(detection.installed)
    detected = tuple(name for name in supported if name in installed)
    not_detected = tuple(name for name in supported if name not in installed)

    gaps: list[InstrumentGap] = [
        InstrumentGap(name, "no certified recipe for this framework") for name in unsupported
    ]

    if not running:
        gaps.extend(
            InstrumentGap(name, "agentwatch recorder not running (no-op)") for name in detected
        )
        report = InstrumentReport(
            detected=detected,
            gaps=tuple(gaps),
            not_detected=not_detected,
            noop=True,
            endpoint=None,
            identity=report_identity,
        )
        if print_report:
            print(report.summary())
        return report

    wiring = wire or _default_wire
    instrumented: list[str] = []
    already: list[str] = []
    for name in detected:
        if name in _INSTRUMENTED:
            already.append(name)
            continue
        recipe = frameworks.RECIPES[name]
        try:
            wiring(recipe, target_endpoint, environ)
        except Exception as exc:  # noqa: BLE001 - a framework must not break the call
            gaps.append(InstrumentGap(name, f"wiring failed: {exc}"))
        else:
            _INSTRUMENTED.add(name)
            instrumented.append(name)

    if not _EXIT_REGISTERED and (instrumented or already):
        register = register_exit or atexit.register
        register(flush_active_provider)
        _EXIT_REGISTERED = True

    report = InstrumentReport(
        detected=detected,
        instrumented=tuple(instrumented),
        gaps=tuple(gaps),
        not_detected=not_detected,
        already=tuple(already),
        noop=False,
        endpoint=target_endpoint,
        identity=report_identity,
    )
    if print_report:
        print(report.summary())
    return report


__all__ = [
    "DEFAULT_HEALTH_ENDPOINT",
    "DEFAULT_OTLP_ENDPOINT",
    "HEALTH_ENDPOINT_ENV",
    "InstrumentGap",
    "InstrumentReport",
    "flush_active_provider",
    "identity_from_env",
    "instrument",
    "reset",
]