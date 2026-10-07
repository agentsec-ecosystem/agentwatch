"""Examples-gallery CI gate (M27 EXA-1 #351).

The gallery is only honest if every recipe either runs in CI or says why it does
not. This test asserts each recipe exists, is indexed in ``examples/README.md``,
and — when marked ``executed`` — runs green against its fixture.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from agentwatch.ocsf import session_ocsf
from agentwatch.records import SecurityEvent, SecurityEventType

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples"
README = EXAMPLES / "README.md"
AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

# recipe path -> (integration, executed?)
RECIPES: dict[str, tuple[str, bool]] = {
    "security_event_consumer.py": ("security-event stream", True),
    "ocsf_consumer.py": ("OCSF 1.5.0", True),
    "claude_agent_sdk_otel.py": ("Claude Agent SDK OTel", True),
    "demo-agent": ("raw Python SDK", False),
}


def test_readme_indexes_every_recipe() -> None:
    text = README.read_text(encoding="utf-8")
    for recipe in RECIPES:
        assert recipe in text, f"{recipe} is not indexed in examples/README.md"
        assert (EXAMPLES / recipe).exists(), f"{recipe} does not exist"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_event_recipe_runs() -> None:
    module = _load("security_event_consumer")
    fixture = EXAMPLES / "fixtures" / "events.ndjson"

    valid, problems = module.validate_events(module.parse_events(fixture.read_text()))

    assert problems == []
    assert [event.type.value for event in valid] == ["denied", "secret-detected"]


def test_ocsf_recipe_runs() -> None:
    module = _load("ocsf_consumer")

    events = [(0, SecurityEvent(type=SecurityEventType.DENIED, emitted_at=AT))]
    text = "\n".join(json.dumps(o) for o in session_ocsf(events, session_id="s1"))

    valid, problems = module.validate_objects(module.parse_objects(text))

    assert problems == []
    assert len(valid) == 1


def test_claude_agent_sdk_recipe_runs() -> None:
    module = _load("claude_agent_sdk_otel")
    fixture = EXAMPLES / "fixtures" / "claude_agent_sdk_otel.json"

    records = module.transcribe(module.load_payload(fixture))

    assert records
    assert all(record["producer"]["name"] == "sdk-native" for record in records)


def test_illustrative_recipe_is_not_required_to_run() -> None:
    # ``demo-agent`` needs external services; the gallery marks it illustrative.
    assert RECIPES["demo-agent"][1] is False
    assert (EXAMPLES / "demo-agent" / "run_demo.py").exists()
