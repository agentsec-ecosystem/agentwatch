"""Skills + command-execution spans (M28 OTEL-4, #362; PRD 41 §OTEL-4).

The GenAI semconv added agent-span operations for skills and command execution.
agentwatch emits them through dedicated helpers where a harness exposes the
behavior, and keeps them out of the pinned upstream vocabulary (a declared gap:
they are agentwatch provisional extensions until upstream adopts them).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentwatch.attrs import (
    AGENT_SPAN_OPERATIONS,
    AGENTWATCH_EXTENSION_OPERATIONS,
    AGENTWATCH_SKILL_NAME,
    AGENTWATCH_SKILL_RESOURCE,
    GEN_AI_OPERATION_NAME,
    GEN_AI_TOOL_NAME,
    SPAN_KIND_EXECUTE_COMMAND,
    SPAN_KIND_LOAD_SKILL,
    SPAN_KIND_READ_SKILL_RESOURCE,
)
from agentwatch.config import SDKConfig
from agentwatch.spans import command_span, skill_span
from agentwatch.tracer import configure_tracing, reset_tracing


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    reset_tracing()
    yield
    reset_tracing()


def _exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    configure_tracing(SDKConfig(), processor=SimpleSpanProcessor(exporter))
    return exporter


def test_operation_vocabulary_is_declared_as_an_extension() -> None:
    assert SPAN_KIND_LOAD_SKILL == "load_skill"
    assert SPAN_KIND_READ_SKILL_RESOURCE == "read_skill_resource"
    assert SPAN_KIND_EXECUTE_COMMAND == "execute_command"
    # The upstream canonical set is untouched; ours is explicitly provisional.
    assert AGENTWATCH_EXTENSION_OPERATIONS == (
        SPAN_KIND_LOAD_SKILL,
        SPAN_KIND_READ_SKILL_RESOURCE,
        SPAN_KIND_EXECUTE_COMMAND,
    )
    assert set(AGENTWATCH_EXTENSION_OPERATIONS).isdisjoint(AGENT_SPAN_OPERATIONS)


def test_load_skill_span() -> None:
    exporter = _exporter()

    with skill_span("pdf"):
        pass

    span = exporter.get_finished_spans()[0]
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_LOAD_SKILL
    assert span.attributes[AGENTWATCH_SKILL_NAME] == "pdf"


def test_read_skill_resource_span() -> None:
    exporter = _exporter()

    with skill_span("pdf", resource="references/REFERENCE.md"):
        pass

    span = exporter.get_finished_spans()[0]
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_READ_SKILL_RESOURCE
    assert span.attributes[AGENTWATCH_SKILL_RESOURCE] == "references/REFERENCE.md"


def test_command_execution_span() -> None:
    exporter = _exporter()

    with command_span("Bash"):
        pass

    span = exporter.get_finished_spans()[0]
    assert span.attributes[GEN_AI_OPERATION_NAME] == SPAN_KIND_EXECUTE_COMMAND
    assert span.attributes[GEN_AI_TOOL_NAME] == "Bash"


def test_command_span_nests_under_an_open_skill_span() -> None:
    exporter = _exporter()

    with skill_span("pdf"), command_span("Bash"):
        pass

    spans = exporter.get_finished_spans()
    skill = next(s for s in spans if s.name == "pdf")
    command = next(s for s in spans if s.name == "Bash")
    skill_ctx = skill.context
    assert skill_ctx is not None
    assert command.context is not None
    assert command.context.trace_id == skill_ctx.trace_id
    assert command.parent is not None
    assert command.parent.span_id == skill_ctx.span_id


FIXTURE = Path(__file__).parent / "fixtures" / "otel" / "skills-commands.json"


def test_fixture_cases_drive_the_helpers() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    exporter = _exporter()

    for case in fixture["cases"]:
        if case["behavior"] == "command":
            with command_span(case["name"]):
                pass
        else:
            with skill_span(case["name"], resource=case.get("resource")):
                pass

    spans = exporter.get_finished_spans()
    operations = [span.attributes[GEN_AI_OPERATION_NAME] for span in spans]
    assert operations == [case["operation"] for case in fixture["cases"]]


def test_harnesses_that_do_not_expose_skills_are_a_declared_gap() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    # An honest gap: a harness whose telemetry does not carry skills/commands is
    # recorded as a gap, never silently treated as "no skill was used".
    assert fixture["declared_gaps"]
    assert all(gap["reason"] for gap in fixture["declared_gaps"])
