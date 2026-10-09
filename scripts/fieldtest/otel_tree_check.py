#!/usr/bin/env python3
"""OTEL-1: the agent-span TREE must render in Jaeger AND Tempo (>=2 backends)."""
from __future__ import annotations

import json
import sys
import time
import urllib.request


def _poll(url: str, want, tries: int = 15, delay: float = 2.0):
    last: Exception | None = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
                data = json.load(response)
            if want(data):
                return data
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(delay)
    if last is not None:
        raise SystemExit(f"unreachable {url}: {last}")
    return None


def _has_child_of(data: dict) -> bool:
    for trace in data.get("data", []):
        for span in trace.get("spans", []):
            if any(ref.get("refType") == "CHILD_OF" for ref in span.get("references", [])):
                return True
    return False


def main() -> int:
    jaeger = _poll(
        "http://localhost:16686/api/traces?service=agentwatch&limit=20", _has_child_of
    )
    if jaeger is None:
        spans = 0
        raise SystemExit(f"no CHILD_OF agent-span tree in Jaeger within timeout (spans={spans})")
    spans = [s for t in jaeger.get("data", []) for s in t.get("spans", [])]
    children = [
        s for s in spans
        if any(ref.get("refType") == "CHILD_OF" for ref in s.get("references", []))
    ]

    tempo = _poll(
        "http://localhost:3200/api/search?tags=service.name%3Dagentwatch",
        lambda d: bool(d.get("traces")),
    )
    if tempo is None:
        raise SystemExit("no traces in Tempo within timeout")
    print(f"ok: Jaeger renders {len(children)} child span(s) of {len(spans)}; "
          f"Tempo holds {len(tempo.get('traces', []))} trace(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
