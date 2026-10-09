#!/usr/bin/env python3
"""OTEL-4: command-execution agent spans from the OTLP fixture are MAPPED into
records (never invented). Every mapped span must trace back to a fixture span."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ftutil import fail, ok, records, run  # noqa: E402

FIXTURE = Path("/ft/fixtures/otel/otel_trace.json")


def _fixture_refs(path: Path) -> tuple[set[str], set[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set()
    ids: set[str] = set()
    traces: set[str] = set()
    for rs in data.get("resourceSpans", []) or []:
        scopes = rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []
        for ss in scopes:
            for span in ss.get("spans", []) or []:
                if span.get("spanId"):
                    ids.add(str(span["spanId"]))
                if span.get("traceId"):
                    traces.add(str(span["traceId"]))
    return ids, traces


def main(argv: list[str]) -> int:
    run(["agentwatch", "ingest", "--format", "otel", str(FIXTURE)])
    run(["agentwatch", "verify-store"])
    ids, traces = _fixture_refs(FIXTURE)
    recs = records()
    if not recs:
        fail("OTLP ingest produced no records")
    stored_ids = {str(r.get("span_id") or "").split(":")[-1] for r in recs}
    stored_traces = {str(r.get("trace_id")) for r in recs}
    mapped = stored_ids & ids
    if not mapped:
        fail(f"no OTLP fixture span mapped (stored_ids={sorted(stored_ids)}, fixture={sorted(ids)})")
    if not (stored_traces & traces):
        fail(f"no fixture trace id mapped (stored={sorted(stored_traces)}, fixture={sorted(traces)})")
    ok(f"mapped {len(mapped)} command-execution agent span(s) from the OTLP fixture "
       f"(trace {sorted(stored_traces & traces)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
