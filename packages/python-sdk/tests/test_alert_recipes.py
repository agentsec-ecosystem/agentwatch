"""Alert-routing recipe CI test (M30 NTF-1, #481).

Three executable recipes (Slack, PagerDuty, Alertmanager) turn agentwatch
security events into each stack's payload and post them through the **existing**
``agentwatch.sinks.WebhookSink`` with an injected transport — so they run in CI
with zero network and prove the routing boundary: agentwatch forwards events
rule-free; the recipes route, and the rules/thresholds live in the user's stack.
"""

from __future__ import annotations

import importlib.util
import json
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

from agentwatch import sinks

REPO = Path(__file__).resolve().parents[3]
RECIPES = REPO / "deploy" / "recipes"
EVENTS = REPO / "examples" / "fixtures" / "events.ndjson"

MODULES = ("slack_webhook", "pagerduty", "alertmanager")


class _Response:
    status = 200

    def read(self) -> bytes:
        return b"ok"


class _Captured:
    def __init__(self) -> None:
        self.requests: list[urllib.request.Request] = []
        self.urls: list[str] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> _Response:
        self.requests.append(request)
        self.urls.append(request.full_url)
        return _Response()


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RECIPES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _events() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in EVENTS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_all_three_recipes_exist_and_reuse_the_shared_sink() -> None:
    for name in MODULES:
        assert (RECIPES / f"{name}.py").is_file(), f"missing recipe {name}.py"
        module = _load(name)
        # Reuse the shipped sink, never a second HTTP implementation.
        assert module.WebhookSink is sinks.WebhookSink


def test_slack_recipe_maps_events_to_incoming_webhook_payloads() -> None:
    module = _load("slack_webhook")
    event = _events()[0]

    payload = module.to_slack(event)

    assert isinstance(payload, dict)
    assert "text" in payload
    assert event["type"] in payload["text"]

    captured = _Captured()
    delivered = module.send([event, _events()[1]], "https://hooks.invalid/x", opener=captured)
    assert delivered == 2
    assert captured.urls == ["https://hooks.invalid/x", "https://hooks.invalid/x"]
    body = json.loads(captured.requests[0].data)
    assert body["text"] == payload["text"]


def test_pagerduty_recipe_maps_events_to_events_api_v2() -> None:
    module = _load("pagerduty")
    event = _events()[1]

    payload = module.to_pagerduty(event, routing_key="rk-demo")

    assert payload["event_action"] == "trigger"
    assert payload["routing_key"] == "rk-demo"
    assert payload["payload"]["source"] == "agentwatch"
    assert payload["dedup_key"].startswith(event["type"])

    captured = _Captured()
    delivered = module.send(
        [event],
        "https://events.invalid/v2/enqueue",
        routing_key="rk-demo",
        opener=captured,
    )
    assert delivered == 1
    sent = json.loads(captured.requests[0].data)
    assert sent["event_action"] == "trigger"


def test_alertmanager_recipe_maps_events_to_the_v2_alerts_api() -> None:
    module = _load("alertmanager")
    event = _events()[0]

    alerts = module.to_alertmanager(event)

    assert isinstance(alerts, list) and alerts
    assert alerts[0]["labels"]["event_type"] == event["type"]
    assert alerts[0]["labels"]["source"] == "agentwatch"
    assert "summary" in alerts[0]["annotations"]

    captured = _Captured()
    delivered = module.send([event], "https://alertmanager.invalid/api/v2/alerts", opener=captured)
    assert delivered == 1
    sent = json.loads(captured.requests[0].data)
    assert sent[0]["labels"]["event_type"] == event["type"]


def test_recipes_forward_every_event_without_builtin_rules() -> None:
    # The recipes must not filter, threshold, or suppress: routing is the user's.
    events = _events()
    for name in MODULES:
        module = _load(name)
        captured = _Captured()
        extra = {"routing_key": "rk-demo"} if name == "pagerduty" else {}
        delivered = module.send(
            events, "https://target.invalid/hook", opener=captured, **extra
        )
        assert delivered == len(events)
        assert len(captured.requests) == len(events)
