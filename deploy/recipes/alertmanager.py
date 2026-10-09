#!/usr/bin/env python3
"""Recipe: agentwatch security events -> Alertmanager v2 alerts (M30 NTF-1).

Copy-and-adapt. agentwatch forwards security events **rule-free**; this recipe
maps each event to an Alertmanager v2 alert and POSTs it to Alertmanager's
``/api/v2/alerts`` endpoint through the shipped ``agentwatch.sinks.WebhookSink``.
It defines **no alert rules**: Alertmanager owns grouping, inhibition, silence
and routing, and every event is forwarded without filtering or suppression.

Run it (no account or network in the CI test)::

    python deploy/recipes/alertmanager.py \
        --input examples/fixtures/events.ndjson \
        --url https://alertmanager.internal/api/v2/alerts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentwatch.sinks import WebhookSink


def _alertname(event_type: str) -> str:
    words = event_type.replace("_", "-").replace(".", "-").split("-")
    return "Agentwatch" + "".join(word.capitalize() for word in words if word)


def to_alertmanager(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Map one agentwatch security event to an Alertmanager v2 alerts payload."""
    event_type = str(event.get("type", "unknown"))
    labels = {
        "alertname": _alertname(event_type),
        "source": "agentwatch",
        "event_type": event_type,
    }
    tool = event.get("tool")
    if tool:
        labels["tool"] = str(tool)
    description = str(event.get("reason") or event_type)
    alert: dict[str, Any] = {
        "labels": labels,
        "annotations": {
            "summary": f"agentwatch security event: {event_type}",
            "description": description,
        },
    }
    if event.get("emitted_at"):
        alert["startsAt"] = event["emitted_at"]
    return [alert]


def send(events: list[dict[str, Any]], url: str, *, opener: Any = None) -> int:
    """Post each event's Alertmanager payload; returns the number delivered."""
    sink = WebhookSink(url, opener=opener)
    delivered = 0
    for event in events:
        sink.deliver(to_alertmanager(event))
        delivered += 1
    return delivered


def _read_events(path: str) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forward agentwatch events to Alertmanager")
    parser.add_argument("--input", required=True, help="NDJSON security-event file")
    parser.add_argument("--url", required=True, help="Alertmanager /api/v2/alerts URL")
    args = parser.parse_args(argv)
    send(_read_events(args.input), args.url)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
