#!/usr/bin/env python3
"""Run the internal detector-eval corpus (M25 DET-1, #302; LLM DET-4).

Offline, deterministic, no network. Drives the real analytics detectors over
``services/analytics/data/detector-corpus-v0.json`` and prints per-detector
precision/recall. CI uses this as the detector-eval gate. Pass ``--include-llm``
to also run the 6 LLM-augmented detectors through the harness (local-model-first;
they degrade to no-op when the local endpoint is unavailable).

Usage::

    python scripts/detector_eval.py [--corpus PATH] [--json] [--include-llm]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "analytics" / "src"))

from analytics.detectors.eval import load_corpus, run_eval  # noqa: E402

DEFAULT_CORPUS = REPO / "services" / "analytics" / "data" / "detector-corpus-v0.json"


def _llm_client():  # type: ignore[no-untyped-def]
    """A local-first OpenAI-compatible client from analytics settings (DET-4)."""
    from analytics.config import settings
    from analytics.llm_client import LLMClient

    return LLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        chat_model=settings.llm_chat_model,
        embed_model=settings.llm_embed_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def _scenario_gate(as_json: bool) -> int:
    """Run the rule detectors over the field-test matrix; gate on >=80% non-silent."""
    from analytics.scenario_validation import rule_coverage, run_rule_matrix

    report = asyncio.run(run_rule_matrix())
    coverage = rule_coverage(report)
    if as_json:
        print(json.dumps({"rule_matrix": report["total"], **coverage}, sort_keys=True))
    else:
        print(
            f"rule-matrix: {report['passed']}/{report['total']} scenarios pass; "
            f"non-silent {coverage['non_silent']}/{coverage['total']} "
            f"({coverage['fraction'] * 100:.1f}%, target {coverage['target'] * 100:.0f}%)"
        )
        if coverage["silent"]:
            print(f"silent: {', '.join(coverage['silent'])}", file=sys.stderr)
    ok = report["failed"] == 0 and coverage["fraction"] >= coverage["target"]
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    include_llm = "--include-llm" in args
    if "--scenarios" in args:
        return _scenario_gate(as_json)
    rest = [arg for arg in args if arg not in ("--json", "--scenarios", "--include-llm")]
    corpus = Path(rest[0]) if rest else DEFAULT_CORPUS

    cases = load_corpus(corpus)
    llm_client = _llm_client() if include_llm else None
    if include_llm and not as_json:
        print(
            "detector-eval: including the 6 LLM detectors (local-model-first; "
            "numbers require a running local endpoint)",
            file=sys.stderr,
        )
    report = run_eval(cases, llm_client=llm_client)
    rows = {
        detector: {
            "precision": round(report.precision(detector), 4),
            "recall": round(report.recall(detector), 4),
        }
        for detector in report.detectors()
    }
    if as_json:
        print(
            json.dumps(
                {"corpus": corpus.name, "include_llm": include_llm, "detectors": rows},
                sort_keys=True,
            )
        )
    else:
        for detector, row in rows.items():
            print(f"{detector}: precision={row['precision']} recall={row['recall']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())