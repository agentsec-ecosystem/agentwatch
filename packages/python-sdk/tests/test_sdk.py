"""SDK provider lifecycle tests (M25 SDK-1, #306).

Contract (design/sdk-lifecycle.md): ``shutdown()`` is at-most-once and never
raises; after shutdown a valid no-op tracer is returned; ``flush(timeout)`` is the
OTel ForceFlush semantic with a bounded result; the context manager flushes on exit.
"""

from __future__ import annotations

from agentwatch.sdk import AgentWatchProvider, FlushResult


class RecordingProcessor:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.flushed: list[float | None] = []
        self.shutdown_count = 0

    def flush(self, timeout: float | None = None) -> bool:
        self.flushed.append(timeout)
        return self.ok

    def shutdown(self) -> None:
        self.shutdown_count += 1


class RaisingProcessor:
    def flush(self, timeout: float | None = None) -> bool:
        raise RuntimeError("boom")

    def shutdown(self) -> None:
        raise RuntimeError("boom")


def test_flush_reports_success_and_passes_timeout() -> None:
    processor = RecordingProcessor(ok=True)
    provider = AgentWatchProvider(processors=[processor])

    result = provider.flush(timeout=1.5)

    assert result.ok is True
    assert result.errors == ()
    assert processor.flushed == [1.5]


def test_flush_reports_failure() -> None:
    processor = RecordingProcessor(ok=False)
    result = AgentWatchProvider(processors=[processor]).flush(timeout=1.0)

    assert result.ok is False
    assert result.errors


def test_shutdown_is_at_most_once() -> None:
    processor = RecordingProcessor()
    provider = AgentWatchProvider(processors=[processor])

    provider.shutdown()
    provider.shutdown()

    assert processor.shutdown_count == 1
    assert provider.is_shutdown is True


def test_shutdown_never_raises_on_a_failing_processor() -> None:
    provider = AgentWatchProvider(processors=[RaisingProcessor()])

    provider.shutdown()  # must not raise

    assert provider.is_shutdown is True


def test_flush_never_raises_and_reports_processor_errors() -> None:
    result = AgentWatchProvider(processors=[RaisingProcessor()]).flush(timeout=1.0)

    assert result.ok is False
    assert any("boom" in error for error in result.errors)


def test_context_manager_flushes_and_shuts_down_on_exit() -> None:
    processor = RecordingProcessor()

    with AgentWatchProvider(processors=[processor]) as provider:
        assert provider.is_shutdown is False

    assert processor.flushed
    assert processor.shutdown_count == 1


def test_tracer_after_shutdown_is_a_noop() -> None:
    provider = AgentWatchProvider()
    provider.shutdown()

    tracer = provider.get_tracer("demo")

    assert tracer.is_noop is True
    with tracer.start_as_current_span("op") as span:
        assert span.is_recording() is False


def test_noop_tracer_never_touches_processors() -> None:
    processor = RecordingProcessor()
    provider = AgentWatchProvider(processors=[processor])
    provider.shutdown()

    with provider.get_tracer("demo").start_as_current_span("op"):
        pass

    assert processor.flushed == []


def test_flush_result_is_truthy_only_when_ok() -> None:
    assert FlushResult(ok=True, errors=()).ok is True
    assert FlushResult(ok=False, errors=("x",)).ok is False


def test_resource_attributes_carry_telemetry_sdk_and_service() -> None:
    from agentwatch.sdk import resource_attributes

    attrs = resource_attributes(service_name="triage")

    assert attrs["telemetry.sdk.name"] == "agentwatch"
    assert attrs["telemetry.sdk.language"] == "python"
    assert attrs["telemetry.sdk.version"]
    assert attrs["service.name"] == "triage"


def test_shutdown_is_thread_safe() -> None:
    import threading

    processor = RecordingProcessor()
    provider = AgentWatchProvider(processors=[processor])
    threads = [threading.Thread(target=provider.shutdown) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert processor.shutdown_count == 1
    assert provider.is_shutdown is True


def test_sampler_is_thread_safe_and_deterministic() -> None:
    import threading
    from datetime import datetime, timezone

    from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall

    record = AgentRecord(
        session_id="s",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        span_id="span-1",
    )
    decisions: list[str] = []
    lock = threading.Lock()

    def decide() -> None:
        from agentwatch.sampling import SecurityRelevantSampler

        value = SecurityRelevantSampler().should_sample(record, ratio=0.5).value
        with lock:
            decisions.append(value)

    threads = [threading.Thread(target=decide) for _ in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(decisions)) == 1