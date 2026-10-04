#!/usr/bin/env python3
"""OTLP export probe (M23 FT-03 / FT-19).

Exercises the SDK's ``agentwatch.tracer`` export path (R4): configure OTLP
tracing for the given endpoint, emit spans under ``service.name=agentwatch``,
flush, and report whether the export plumbing completed without raising.

The probe deliberately returns **0 even when the endpoint is down**: an
unreachable backend must never break the instrumented agent (F5). The runner
asserts delivery separately by querying the backend.

Runs inside the recorder container (the recorder image installs agentsec-agentwatch[otlp]).
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/work/packages/python-sdk/src")

from agentwatch.config import SDKConfig  # noqa: E402
from agentwatch.tracer import configure_otlp_tracing, get_tracer  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True, help="OTLP gRPC endpoint, e.g. http://jaeger:4317")
    parser.add_argument("--service", default="agentwatch")
    parser.add_argument("--spans", type=int, default=3)
    args = parser.parse_args(argv)

    config = SDKConfig(service_name=args.service, otlp_endpoint=args.endpoint)
    try:
        provider = configure_otlp_tracing(config, endpoint=args.endpoint)
    except ImportError as exc:  # missing otlp extra in the image
        print(f"otel-probe: OTLP exporter unavailable: {exc}", file=sys.stderr)
        return 2

    tracer = get_tracer("agentwatch.probe")
    for index in range(args.spans):
        with tracer.start_as_current_span(f"ft-probe-{index}") as span:
            span.set_attribute("gen_ai.agent.name", "ft-probe")
            span.set_attribute("agentwatch.seq", index)

    # Flush so a short-lived process does not lose the batch. Export errors are
    # swallowed by the SDK's exporter; the probe must not fail the agent.
    try:
        provider.force_flush(timeout_millis=5000)
    except Exception as exc:  # noqa: BLE001 - exporter failure must not break the agent
        print(f"otel-probe: flush raised (endpoint down?): {exc}", file=sys.stderr)

    print(f"otel-probe: {args.spans} spans emitted to {args.endpoint} as {args.service}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
