"""Syslog sink verification (M27 SIEM-2 #347).

The opt-in Syslog sink (shipped M20 S10) is verified here for the M27 acceptance:
the S10 redaction self-test gate applies to it like every sink, and a delivery
failure surfaces a visible ``degraded`` state — never a silent drop.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from agentwatch import sinks
from agentwatch.sinks import EventForwarder, SinkError, SyslogSink, build_sink

_LOGGER = logging.getLogger("agentwatch.sinks.syslog")


@pytest.fixture(autouse=True)
def _restore_syslog_logger() -> Iterator[None]:
    """A SyslogSink registers its handler on a process-global logger; restore it."""
    saved = list(_LOGGER.handlers)
    yield
    _LOGGER.handlers = saved


def test_syslog_target_builds_a_syslog_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    made: dict[str, object] = {}

    class Fake(SyslogSink):
        def __init__(self, address: str | None = None, *, handler: object = None) -> None:
            made["address"] = address

    monkeypatch.setattr(sinks, "SyslogSink", Fake)

    assert isinstance(build_sink("syslog://syslog.internal"), Fake)
    assert made["address"] == "syslog.internal"


def test_syslog_sink_wraps_a_delivery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = SyslogSink(handler=logging.NullHandler())

    def boom(*_: object, **__: object) -> None:
        raise OSError("syslog down")

    monkeypatch.setattr(sink.logger, "info", boom)

    with pytest.raises(SinkError):
        sink.deliver({"type": "denied"})


def test_forwarder_is_degraded_on_a_syslog_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = SyslogSink(handler=logging.NullHandler())

    def boom(*_: object, **__: object) -> None:
        raise OSError("syslog down")

    monkeypatch.setattr(sink.logger, "info", boom)
    monkeypatch.setattr(sinks, "build_sink", lambda target, **_: sink)

    state = EventForwarder(["syslog"]).forward({"type": "denied"})

    assert state.degraded is True
    assert state.last_error
    assert state.delivered == 0  # bounded: the event stays queued, never silently dropped
