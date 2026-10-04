"""Opt-in security-event forwarding sinks (M20 S10, PRD 36).

Consumers need a path *out* that is not "stand up an OTLP collector": an
auditor's file drop, a 20-line webhook bridge, syslog. Sinks forward **security
events only — never full records**, and only when explicitly enabled in config
and the redaction self-test passes (R6/DD-09).

Hard rule: a sink has **no filtering beyond event type** — no rules, no
thresholds, no routing. Forwarding is not alerting. A delivery failure is a
visible ``degraded`` state with a bounded queue, never a silent drop and never an
unbounded retry.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import socket
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

FILE_SCHEME = "file://"
SYSLOG_SCHEME = "syslog"
DEFAULT_QUEUE_SIZE = 256
WEBHOOK_TIMEOUT_SECONDS = 5.0


class SinkError(RuntimeError):
    """Raised by a sink when an event could not be delivered."""


@runtime_checkable
class EventSink(Protocol):
    """A security-event destination; raises :class:`SinkError` on failure."""

    def deliver(self, event: dict[str, Any]) -> None: ...


def event_bytes(event: Mapping[str, Any]) -> bytes:
    """Canonical one-line JSON for an event (``unmapped`` etc. preserved)."""
    return (json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


class FileSink:
    """Append events as NDJSON to a local file (``file:///path/events.ndjson``)."""

    def __init__(self, path: str) -> None:
        from pathlib import Path

        self.path = Path(path)

    def deliver(self, event: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as handle:
                handle.write(event_bytes(event))
        except OSError as exc:
            raise SinkError(f"file sink {self.path}: {exc}") from exc


class WebhookSink:
    """POST one event to an HTTPS endpoint; failure raises (bounded by the caller)."""

    def __init__(
        self, url: str, *, opener: Callable[[urllib.request.Request, float], Any] | None = None
    ) -> None:
        self.url = url
        self._opener = opener or self._default_opener

    @staticmethod
    def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310

    def deliver(self, event: dict[str, Any]) -> None:
        request = urllib.request.Request(  # noqa: S310
            self.url,
            data=event_bytes(event),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            self._opener(request, WEBHOOK_TIMEOUT_SECONDS)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SinkError(f"webhook sink {self.url}: {exc}") from exc


class SyslogSink:
    """Emit one event per syslog message (``syslog`` or ``syslog://host``)."""

    def __init__(
        self, address: str | None = None, *, handler: logging.Handler | None = None
    ) -> None:
        self.address = address
        self.logger = logging.getLogger("agentwatch.sinks.syslog")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if handler is not None:
            self._handler = handler
        else:  # pragma: no cover - network syslog path
            self._handler = logging.handlers.SysLogHandler(address=self._resolve_address(address))
        if not self.logger.handlers:
            self.logger.addHandler(self._handler)

    @staticmethod
    def _resolve_address(address: str | None) -> tuple[str, int] | str:
        if not address:
            return "/dev/log" if hasattr(socket, "AF_UNIX") else ("localhost", 514)
        return (address, 514)

    def deliver(self, event: dict[str, Any]) -> None:
        try:
            self.logger.info(event_bytes(event).decode("utf-8").strip())
        except (OSError, ValueError) as exc:  # pragma: no cover - syslog failure
            raise SinkError(f"syslog sink: {exc}") from exc


def build_sink(target: str, *, webhook_opener: Callable[..., Any] | None = None) -> EventSink:
    """Build a sink from a config target string, or raise :class:`SinkError`."""
    if target.startswith(FILE_SCHEME):
        return FileSink(target[len(FILE_SCHEME) :])
    if target.startswith(("https://", "http://")):
        return WebhookSink(target, opener=webhook_opener)
    if target == SYSLOG_SCHEME or target.startswith(SYSLOG_SCHEME + "://"):
        address = target[len(SYSLOG_SCHEME) + 3 :] or None
        return SyslogSink(address)
    raise SinkError(f"unsupported sink target: {target!r}")


@dataclass
class DeliveryState:
    """The forwarder's visible health: delivered, queued, and degraded."""

    delivered: int = 0
    queued: int = 0
    degraded: bool = False
    last_error: str | None = None


class EventForwarder:
    """Forward security events to all sinks with a bounded queue and visible failure."""

    def __init__(
        self,
        targets: Sequence[str],
        *,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        webhook_opener: Callable[..., Any] | None = None,
    ) -> None:
        self.sinks: list[EventSink] = [
            build_sink(target, webhook_opener=webhook_opener) for target in targets
        ]
        self._queue: deque[dict[str, Any]] = deque(maxlen=queue_size)
        self.state = DeliveryState()

    def forward(self, event: Mapping[str, Any]) -> DeliveryState:
        """Enqueue then drain; never raises (a sink failure is ``degraded``)."""
        self._queue.append(dict(event))
        self._drain()
        self.state.queued = len(self._queue)
        return self.state

    def _drain(self) -> None:
        while self._queue:
            event = self._queue[0]
            for sink in self.sinks:
                try:
                    sink.deliver(event)
                except SinkError as exc:
                    # Bounded: the event stays at the head and is retried later.
                    self.state.degraded = True
                    self.state.last_error = str(exc)
                    return
            self._queue.popleft()
            self.state.delivered += 1
        self.state.degraded = False
        self.state.last_error = None


__all__ = [
    "DEFAULT_QUEUE_SIZE",
    "DeliveryState",
    "EventForwarder",
    "EventSink",
    "FileSink",
    "SinkError",
    "SyslogSink",
    "WebhookSink",
    "build_sink",
    "event_bytes",
]
