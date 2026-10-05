#!/usr/bin/env python3
"""Emit an agent-span tree to a real OTLP backend and capture it as evidence (M25).

Milestone-exit evidence for the WBS bullet "OTel agent-span tree renders in ≥1
reference backend". This drives the SDK's own ``configure_otlp_tracing`` export
path against the local Jaeger/collector stack, then reads the trace back from the
Jaeger HTTP API and writes:

* ``docs/release/v0.2.0/m25-otel-agent-span-tree.json``  (raw Jaeger trace)
* ``docs/release/v0.2.0/m25-otel-agent-span-tree.md``    (rendered tree + provenance)

Usage::

    docker compose up -d jaeger otel-collector
    PYTHONPATH=packages/python-sdk/src python3 scripts/m25_otel_backend_evidence.py

Environment overrides: ``OTLP_ENDPOINT`` (default http://localhost:4317),
``JAEGER_URL`` (default http://localhost:16686).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from opentelemetry.trace import Status, StatusCode  # noqa: E402

from agentwatch.config import SDKConfig  # noqa: E402
from agentwatch.tracer import configure_otlp_tracing, get_tracer  # noqa: E402

SERVICE = "agentwatch-m25-evidence"
CONVERSATION = "conv-m25-evidence"
OUT_JSON = REPO / "docs" / "release" / "v0.2.0" / "m25-otel-agent-span-tree.json"
OUT_MD = REPO / "docs" / "release" / "v0.2.0" / "m25-otel-agent-span-tree.md"


def emit() -> int:
    endpoint = os.environ.get("OTLP_ENDPOINT", "http://localhost:4317")
    config = SDKConfig(service_name=SERVICE, otlp_endpoint=endpoint)
    provider = configure_otlp_tracing(config, endpoint=endpoint)
    tracer = get_tracer("agentwatch")

    def tool(name: str, tokens: int, *, error: bool = False) -> None:
        with tracer.start_as_current_span("execute_tool") as span:
            span.set_attribute("gen_ai.operation.name", "execute_tool")
            span.set_attribute("gen_ai.tool.name", name)
            span.set_attribute("gen_ai.usage.total_tokens", tokens)
            if error:
                span.set_attribute("error.type", "tool_error")
                span.set_status(Status(StatusCode.ERROR, "tool failed"))

    with tracer.start_as_current_span("invoke_agent") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        root.set_attribute("gen_ai.agent.name", "request_triage")
        root.set_attribute("gen_ai.agent.version", "v1.0")
        root.set_attribute("gen_ai.conversation.id", CONVERSATION)
        with tracer.start_as_current_span("plan") as plan:
            plan.set_attribute("gen_ai.operation.name", "plan")
            plan.set_attribute("gen_ai.request.model", "claude-opus-4-7")
        tool("lookup_account", 120)
        tool("search_kb", 87)
        with tracer.start_as_current_span("create_agent") as sub:
            sub.set_attribute("gen_ai.operation.name", "create_agent")
            sub.set_attribute("gen_ai.agent.name", "triage-subagent")
            tool("escalate", 41, error=True)

    provider.force_flush()
    provider.shutdown()
    return 0


def fetch_trace(jaeger_url: str, *, attempts: int = 20, delay: float = 1.0) -> dict[str, Any]:
    url = f"{jaeger_url}/api/traces?service={SERVICE}&limit=5&lookback=1h"
    last: Exception | None = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
            if data.get("data"):
                return data["data"][0]
        except (urllib.error.URLError, OSError, ValueError) as exc:  # pragma: no cover
            last = exc
        time.sleep(delay)
    raise SystemExit(f"trace not found in Jaeger after {attempts} attempts: {last}")


def _tags(span: dict[str, Any]) -> dict[str, Any]:
    return {tag["key"]: tag["value"] for tag in span.get("tags", [])}


def render(trace: dict[str, Any], process: str) -> str:
    spans = trace["spans"]
    by_id = {span["spanID"]: span for span in spans}
    children: dict[str | None, list[str]] = {}
    for span in spans:
        parent = None
        for ref in span.get("references", []):
            if ref.get("refType") == "CHILD_OF":
                parent = ref["spanID"]
        children.setdefault(parent, []).append(span["spanID"])

    lines: list[str] = []

    def walk(span_id: str, depth: int) -> None:
        span = by_id[span_id]
        tags = _tags(span)
        detail = tags.get("gen_ai.agent.name") or tags.get("gen_ai.tool.name") or ""
        duration = span.get("duration", 0) / 1000
        suffix = f" [{detail}]" if detail else ""
        lines.append(f"{'  ' * depth}- `{span['operationName']}`{suffix} ({duration:.1f} ms)")
        for child in sorted(children.get(span_id, [])):
            walk(child, depth + 1)

    roots = [span["spanID"] for span in spans if not any(
        ref.get("refType") == "CHILD_OF" for ref in span.get("references", [])
    )]
    for root in roots:
        walk(root, 0)
    return "\n".join(lines)


def main() -> int:
    emit()
    jaeger_url = os.environ.get("JAEGER_URL", "http://localhost:16686")
    trace = fetch_trace(jaeger_url)
    process = trace["processes"].get(trace["spans"][0]["processID"], {}).get("serviceName", SERVICE)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tree = render(trace, process)
    OUT_MD.write_text(
        "# M25 evidence — OTel agent-span tree in a reference backend\n\n"
        f"Trace `{trace['traceID']}` from service `{process}`, exported through the SDK's\n"
        "`configure_otlp_tracing` path to the local collector (`:4317`) and rendered from the\n"
        "Jaeger HTTP API. Raw trace: `m25-otel-agent-span-tree.json`.\n\n"
        "```\n" + tree + "\n```\n",
        encoding="utf-8",
    )
    print(f"trace {trace['traceID']} ({len(trace['spans'])} spans) from {process}")
    print(tree)
    print(f"wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
