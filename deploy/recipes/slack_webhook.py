#!/usr/bin/env python3
"""Recipe: agentwatch security events -> Slack incoming webhook (M30 NTF-1).

Copy-and-adapt. agentwatch forwards security events **rule-free** (``agentwatch
sinks``); this recipe is the user's routing layer: it turns each event into a
Slack incoming-webhook payload and posts it through the shipped
``agentwatch.sinks.WebhookSink``. There are **no built-in rules, thresholds, or
severities here** — every event is forwarded; filtering/paging is yours.

Run it (needs the SDK importable; no account or network in the CI test)::

    python deploy/recipes/slack_webhook.py \
        --input examples/fixtures/events.ndjson \
        --url https://hooks.slack.com/services/...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentwatch.sinks import WebhookSink


def to_slack(event: dict[str, Any]) -> dict[str, Any]:
    """Map one agentwatch security event to a Slack incoming-webhook payload."""
    event_type = str(event.get("type", "unknown"))
    parts = [f"agentwatch {event_type}"]
    tool = event.get("tool")
    if tool:
        parts.append(f"tool={tool}")
    reason = event.get("reason")
    if reason:
        parts.append(str(reason))
    return {"text": " — ".join(parts)}


def send(events: list[dict[str, Any]], url: str, *, opener: Any = None) -> int:
    """Post each event's Slack payload; returns the number delivered."""
    sink = WebhookSink(url, opener=opener)
    delivered = 0
    for event in events:
        sink.deliver(to_slack(event))
        delivered += 1
    return delivered


def _read_events(path: str) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forward agentwatch events to Slack")
    parser.add_argument("--input", required=True, help="NDJSON security-event file")
    parser.add_argument("--url", required=True, help="Slack incoming-webhook URL")
    args = parser.parse_args(argv)
    send(_read_events(args.input), args.url)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
