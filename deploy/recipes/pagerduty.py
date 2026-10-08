#!/usr/bin/env python3
"""Recipe: agentwatch security events -> PagerDuty Events API v2 (M30 NTF-1).

Copy-and-adapt. agentwatch forwards security events **rule-free**; this recipe
maps each event to a PagerDuty Events API v2 payload and posts it through the
shipped ``agentwatch.sinks.WebhookSink``. It defines **no alert rules**: the
event-to-urgency mapping below is a presentation default you own and should
edit; forwarding never filters or suppresses an event.

Run it (no account or network in the CI test)::

    python deploy/recipes/pagerduty.py \
        --input examples/fixtures/events.ndjson \
        --url https://events.pagerduty.com/v2/enqueue \
        --routing-key "$PAGERDUTY_ROUTING_KEY"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentwatch.sinks import WebhookSink

# Presentation default only — the user's routing stack owns urgency, not agentwatch.
_SEVERITY = {
    "secret-detected": "critical",
    "denied": "warning",
    "policy-fired": "warning",
    "capability-changed": "info",
    "mode-transition": "info",
}

_CUSTOM_FIELDS = ("event_version", "type", "tool", "reason", "policy_id", "emitted_at")


def to_pagerduty(
    event: dict[str, Any], *, routing_key: str, severity: str | None = None
) -> dict[str, Any]:
    """Map one agentwatch security event to a PagerDuty Events API v2 payload."""
    event_type = str(event.get("type", "unknown"))
    tool = event.get("tool")
    dedup_key = f"{event_type}:{tool or 'none'}"
    summary = f"agentwatch {event_type}" + (f" ({tool})" if tool else "")
    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {
            "summary": summary,
            "source": "agentwatch",
            "severity": severity or _SEVERITY.get(event_type, "info"),
            "timestamp": event.get("emitted_at"),
            "custom_details": {key: event[key] for key in _CUSTOM_FIELDS if key in event},
        },
    }


def send(
    events: list[dict[str, Any]],
    url: str,
    *,
    routing_key: str,
    opener: Any = None,
) -> int:
    """Post each event's PagerDuty payload; returns the number delivered."""
    sink = WebhookSink(url, opener=opener)
    delivered = 0
    for event in events:
        sink.deliver(to_pagerduty(event, routing_key=routing_key))
        delivered += 1
    return delivered


def _read_events(path: str) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forward agentwatch events to PagerDuty")
    parser.add_argument("--input", required=True, help="NDJSON security-event file")
    parser.add_argument("--url", default="https://events.pagerduty.com/v2/enqueue")
    parser.add_argument("--routing-key", required=True)
    args = parser.parse_args(argv)
    send(_read_events(args.input), args.url, routing_key=args.routing_key)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
