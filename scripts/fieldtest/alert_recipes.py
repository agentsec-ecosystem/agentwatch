#!/usr/bin/env python3
"""M31 31.2 — alert-routing recipes (NTF-1).

Exercises the three shipped recipes (Slack incoming webhook, PagerDuty Events
API v2, Prometheus Alertmanager v2) the same way the CI test
(``packages/python-sdk/tests/test_alert_recipes.py``) does: each recipe reuses
the shipped ``agentwatch.sinks.WebhookSink`` and forwards **every** event
through it with an injected transport (zero network), proving the routing
boundary — agentwatch forwards events rule-free; routing lives in the user's
stack.

The canonical recipes are bind-mounted from ``deploy/recipes`` at ``/ft/recipes``.
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import sinks  # real API
from _ftutil import ok

RECIPES = Path("/ft/recipes")
MODULES = ("slack_webhook", "pagerduty", "alertmanager")

# The same security-event shape the recipes are shipped to route.
EVENTS = [
    {
        "event_version": "0.1.0",
        "type": "denied",
        "emitted_at": "2026-01-02T03:04:05+00:00",
        "emitter": "agentwatch",
        "tool": "Bash",
        "reason": "user denied the command",
    },
    {
        "event_version": "0.1.0",
        "type": "secret-detected",
        "emitted_at": "2026-01-02T03:04:06+00:00",
        "emitter": "agentwatch",
        "evidence": {"kinds": ["api-key"]},
    },
]


class _Response:
    status = 200

    def read(self) -> bytes:
        return b"ok"


class _Captured:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return _Response()


def _load(name):
    spec = importlib.util.spec_from_file_location(name, RECIPES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None, name
    spec.loader.exec_module(module)
    return module


def main(argv):
    for name in MODULES:
        module = _load(name)
        # The recipes reuse the shipped sink, never a second HTTP implementation.
        assert module.WebhookSink is sinks.WebhookSink, name
        captured = _Captured()
        extra = {"routing_key": "rk-demo"} if name == "pagerduty" else {}
        delivered = module.send(
            EVENTS, "https://target.invalid/hook", opener=captured, **extra
        )
        # No built-in rules: every event is forwarded, none filtered/suppressed.
        assert delivered == len(EVENTS), name
        assert len(captured.requests) == len(EVENTS), name
    ok(f"three routing recipes forward every event rule-free: {', '.join(MODULES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
