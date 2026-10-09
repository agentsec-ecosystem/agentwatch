"""Claude Agent SDK / headless via the native telemetry path (M29 CCO-2, #445).

The Agent SDK runs the same CLI and emits the same OTel; through the shared
``claude_otel`` path it lands as ``producer.name=sdk-native`` with identity from
the resource attributes. The gallery recipe runs in CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from agentwatch import compatibility
from agentwatch.claude_otel import SDK_PRODUCER, transcode_agent_sdk
from agentwatch.records import ProducerKind

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples"
FIXTURE = EXAMPLES / "fixtures" / "claude_agent_sdk_otel.json"
RECIPE = EXAMPLES / "claude_agent_sdk_otel.py"


def _load_recipe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("claude_agent_sdk_otel", RECIPE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_sdk_uses_the_same_path_with_sdk_native_producer() -> None:
    payload = _load_recipe().load_payload(FIXTURE)
    records, problems = transcode_agent_sdk(payload, source="sdk-native")

    assert problems == []
    assert records
    for record in records:
        assert record.producer is not None
        assert record.producer.kind is ProducerKind.SDK
        assert record.producer.name == SDK_PRODUCER.name == "sdk-native"


def test_agent_sdk_identity_comes_from_resource_attributes() -> None:
    payload = _load_recipe().load_payload(FIXTURE)
    records, _ = transcode_agent_sdk(payload)
    assert {record.agent.identity for record in records} == {"agent-sdk-worker"}


def test_agent_sdk_tool_decision_maps_to_classifier() -> None:
    payload = _load_recipe().load_payload(FIXTURE)
    records, _ = transcode_agent_sdk(payload)
    decision = next(record for record in records if record.tool.name == "Bash")
    assert decision.authorization is not None
    assert decision.authorization.source.value == "classifier"


def test_gallery_recipe_is_indexed_and_runs() -> None:
    module = _load_recipe()
    readme = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    assert "claude_agent_sdk_otel.py" in readme

    records = module.transcribe(module.load_payload(FIXTURE))

    assert records
    assert all(record["producer"]["name"] == "sdk-native" for record in records)


def test_agent_sdk_is_in_the_framework_matrix() -> None:
    row = compatibility.framework("claude-agent-sdk")
    assert row.tier
    assert row.tier in ("Tier-1", "Tier-2")
    assert "sdk-native" in row.invocation


def test_framework_matrix_is_rendered_into_the_doc() -> None:
    table = compatibility.render_table()
    assert "`claude-agent-sdk`" in table
    doc = (REPO_ROOT / "docs" / "reference" / "compatibility.md").read_text(encoding="utf-8")
    assert compatibility.render_marker_block() in doc
