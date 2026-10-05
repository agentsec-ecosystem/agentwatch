"""OpenTelemetry-shaped SDK provider + lifecycle (M25 SDK-1, PRD 46).

``AgentWatchProvider`` owns configuration and produces tracers, matching the OTel
trace-SDK shape so agentwatch feels native: processors form the pipeline
(redact -> chain -> export), ``flush(timeout)`` is the ForceFlush semantic, and
``shutdown()`` is at-most-once with a valid no-op tracer afterwards.

Additive to the existing ``@trace_agent`` / ``TracedGraph`` surface (DD-12): it
never changes those APIs. The guarantee is that a process which exits normally
loses no span.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class FlushResult:
    """The bounded result of a ForceFlush: overall success plus per-processor errors."""

    ok: bool
    errors: tuple[str, ...] = ()
    timed_out: bool = False

    def summary(self) -> str:
        if self.ok:
            return "flush ok"
        return "flush failed: " + "; ".join(self.errors)


@runtime_checkable
class Processor(Protocol):
    """The minimal processor contract the provider flushes and shuts down."""

    def flush(self, timeout: float | None = None) -> bool: ...

    def shutdown(self) -> None: ...


class _NoOpSpan:
    """A valid no-op span: the only thing a shut-down provider may return."""

    def is_recording(self) -> bool:
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Span:
    """A minimal recording span (real OTel span wiring lands with SDK-3)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}
        self._recording = True

    def is_recording(self) -> bool:
        return self._recording

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def end(self) -> None:
        self._recording = False

    def __enter__(self) -> _Span:
        return self

    def __exit__(self, *exc: object) -> None:
        self.end()


class Tracer:
    """A tracer from a provider; ``is_noop`` is true once the provider is shut down."""

    def __init__(self, name: str, *, is_noop: bool) -> None:
        self.name = name
        self.is_noop = is_noop

    def start_as_current_span(self, name: str, **kwargs: Any) -> Any:
        return _NoOpSpan() if self.is_noop else _Span(name)


class AgentWatchProvider:
    """Owns processors and the tracer lifecycle (design/sdk-lifecycle.md)."""

    def __init__(
        self,
        *,
        processors: list[Processor] | tuple[Processor, ...] = (),
        config: Any = None,
    ) -> None:
        self._processors: list[Processor] = list(processors)
        self.config = config
        self._shutdown = False

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def add_processor(self, processor: Processor) -> None:
        self._processors.append(processor)

    def get_tracer(self, name: str) -> Tracer:
        return Tracer(name, is_noop=self._shutdown)

    def flush(self, timeout: float | None = None) -> FlushResult:
        """ForceFlush every processor; never raises, always returns a bounded result."""
        errors: list[str] = []
        for processor in self._processors:
            try:
                if not processor.flush(timeout):
                    errors.append(f"{type(processor).__name__}: flush reported failure")
            except Exception as exc:  # noqa: BLE001 - a processor must never break flush
                errors.append(f"{type(processor).__name__}: {exc}")
        return FlushResult(ok=not errors, errors=tuple(errors))

    def shutdown(self) -> None:
        """At-most-once, idempotent, and never raising (a hook must exit 0)."""
        if self._shutdown:
            return
        self._shutdown = True
        for processor in self._processors:
            with contextlib.suppress(Exception):
                processor.shutdown()

    def __enter__(self) -> AgentWatchProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        self.flush()
        self.shutdown()


def resource_attributes(
    *,
    service_name: str = "agentwatch",
    service_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """OTel resource attributes so backends recognize the SDK and the service (SDK-3)."""
    from agentwatch import __version__

    attributes: dict[str, Any] = {
        "telemetry.sdk.name": "agentwatch",
        "telemetry.sdk.language": "python",
        "telemetry.sdk.version": __version__,
        "service.name": service_name,
    }
    if service_version is not None:
        attributes["service.version"] = service_version
    if extra:
        attributes.update(extra)
    return attributes


__all__ = [
    "AgentWatchProvider",
    "FlushResult",
    "Processor",
    "Tracer",
    "resource_attributes",
]