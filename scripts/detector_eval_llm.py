#!/usr/bin/env python3
"""Publish LLM-detector precision/recall on the shared harness (M27 DET-4, #343).

Runs the 6 LLM-augmented detectors through the same offline harness (local-model-first)
over a small chat-based corpus and writes their per-detector numbers with the
method and model. Requires a running local OpenAI-compatible endpoint (the MLX
server by default); without one the chat detectors degrade to no-op and the
numbers are all zero. ``output_drift`` (an embeddings detector) needs an
embeddings endpoint and is excluded.

Usage::

    python scripts/detector_eval_llm.py [--json-out PATH] [--json]
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "analytics" / "src"))

from analytics.config import settings  # noqa: E402
from analytics.detectors import create_llm_detectors  # noqa: E402
from analytics.detectors.eval import DetectorCase, run_eval  # noqa: E402
from analytics.llm_client import LLMClient  # noqa: E402
from analytics.models import RunSummary, SpanNode  # noqa: E402

CORPUS = REPO / "services" / "analytics" / "data" / "detector-llm-corpus-v0.json"
OUT = REPO / "docs" / "reference" / "detector-llm-numbers.json"


def _cases() -> list[DetectorCase]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases: list[DetectorCase] = []
    for spec in data.get("cases", []):
        spans = [
            SpanNode(
                span_id=f"{spec['id']}-{index}",
                trace_id=str(spec["id"]),
                operation_name=str(span.get("operation", "invoke_agent")),
                attributes=dict(span.get("attrs", {})),
            )
            for index, span in enumerate(spec.get("spans", []))
        ]
        cases.append(
            DetectorCase(
                id=str(spec["id"]),
                summary=RunSummary(
                    run_id=str(spec["id"]), agent_name="llm-corpus", agent_version="v0"
                ),
                spans=spans,
                expected=frozenset(str(name) for name in spec.get("expected", [])),
            )
        )
    return cases


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    out = OUT
    if "--json-out" in args:
        out = Path(args[args.index("--json-out") + 1])

    client = LLMClient()
    cases = _cases()
    report = run_eval(cases, detectors=create_llm_detectors(client))

    detectors = {
        detector: {
            "precision": round(report.precision(detector), 4),
            "recall": round(report.recall(detector), 4),
        }
        for detector in report.detectors()
    }
    payload: dict[str, Any] = {
        "suite": "llm-detectors",
        "harness": "analytics.detectors.eval.run_eval",
        "corpus": CORPUS.name,
        "cases": len(cases),
        "model": settings.llm_chat_model,
        "local_endpoint": settings.llm_base_url,
        "generated": date.today().isoformat(),
        "note": "local-model-first; output_drift (embeddings) excluded — no embeddings endpoint",
        "detectors": detectors,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        for detector, row in detectors.items():
            print(f"{detector}: precision={row['precision']} recall={row['recall']}")
        print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
