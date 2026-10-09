#!/usr/bin/env python3
"""Score LLM detector telemetry from FT-11b/11d corpus runs.

Reads ``llm_responses.jsonl`` and ``traces.json`` from each case's artifacts
and computes per-detector, per-model telemetry: call counts, error rates,
JSON parse rates, verdict distribution (positive/negative), latency percentiles,
token usage, and LLM-verdict vs pipeline-output agreement.

True TPR/FPR comes from FT-15's scenario matrix (ground-truth labels); this
script reports the corpus-run telemetry that FT-11b/11d provide.

Usage::

    python3 scripts/fieldtest/score-llm-telemetry.py \\
        field-test/v0.1.0/results/all/cases/FT-11b/artifacts/llm/with-llm \\
        field-test/v0.1.0/results/all/cases/FT-11d/artifacts/llm/with-llm \\
        --out field-test/v0.1.0/results/ft15/cases/FT-15/artifacts/llm-telemetry.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


POSITIVE_KEYS = {
    "semantic_loop": "identical",
    "hallucination": "hallucination",
    "goal_drift": "diverged",
    "quality_degradation": "degraded",
    "confusion_pattern": "contradiction",
}
# output_drift (EmbeddingDrift) returns {"similarity": float}; low = drift.


def _parse_response(detector: str, raw: str) -> dict | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed


def _is_positive(detector: str, parsed: dict) -> bool:
    if detector in POSITIVE_KEYS:
        key = POSITIVE_KEYS[detector]
        return parsed.get(key) is True
    if detector == "output_drift":
        sim = parsed.get("similarity")
        if sim is not None:
            return float(sim) < 0.7
    return False


def _pctile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return sorted_vals[idx]


def score_dir(dir_path: Path) -> dict:
    """Score one FT-11b/11d artifact directory."""
    responses_path = dir_path / "llm_responses.jsonl"
    traces_path = dir_path / "traces.json"
    summary_path = dir_path / "summary.json"

    if not responses_path.exists():
        return {"error": f"no llm_responses.jsonl in {dir_path}"}

    # Load LLM responses
    responses: list[dict] = []
    for line in responses_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            responses.append(json.loads(line))

    # Load traces (pipeline output — what actually fired)
    traces: list[dict] = []
    if traces_path.exists():
        traces = json.loads(traces_path.read_text(encoding="utf-8"))

    # Build per-trace detected anomaly types from traces.json
    detected_by_trace: dict[str, set[str]] = {}
    for t in traces:
        tid = t.get("trace_id", "")
        detected_by_trace[tid] = {
            a.get("type", "") for a in t.get("anomalies", []) if isinstance(a, dict)
        }

    # Load summary for aggregate stats
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Per-detector telemetry
    by_det: dict[str, list[dict]] = defaultdict(list)
    for r in responses:
        by_det[r.get("detector", "")].append(r)

    det_stats: dict[str, dict] = {}
    for det, recs in sorted(by_det.items()):
        total = len(recs)
        parsed_ok = 0
        positive = 0
        negative = 0
        parse_fail = 0
        latencies: list[float] = []
        prompt_tokens: list[int] = []
        completion_tokens: list[int] = []

        for r in recs:
            raw = r.get("response", "")
            parsed = _parse_response(det, raw)
            if parsed is not None:
                parsed_ok += 1
                if _is_positive(det, parsed):
                    positive += 1
                else:
                    negative += 1
            else:
                parse_fail += 1

        # LLM verdict vs pipeline agreement
        # For each trace, did the LLM say positive? Did the pipeline detect it?
        tp = fp = fn = tn = 0
        for r in recs:
            tid = r.get("trace_id", "")
            raw = r.get("response", "")
            parsed = _parse_response(det, raw)
            llm_pos = parsed is not None and _is_positive(det, parsed)
            pipeline_det = det in detected_by_trace.get(tid, set())
            # Note: detector anomaly_type may differ from detector class name
            # Map: semantic_loop -> semantic_loop, hallucination -> hallucination, etc.
            if llm_pos and pipeline_det:
                tp += 1
            elif llm_pos and not pipeline_det:
                fp += 1
            elif not llm_pos and pipeline_det:
                fn += 1
            else:
                tn += 1

        det_stats[det] = {
            "total_calls": total,
            "parsed_ok": parsed_ok,
            "parse_fail": parse_fail,
            "positive_verdicts": positive,
            "negative_verdicts": negative,
            "parse_rate": round(parsed_ok / total * 100, 1) if total else 0,
            "positive_rate": round(positive / total * 100, 1) if total else 0,
            "llm_vs_pipeline": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        }

    # Aggregate LLM stats from summary
    llm_stats = summary.get("llm_stats", {})
    llm_telemetry = summary.get("llm_telemetry_summary", {})

    return {
        "dir": str(dir_path),
        "traces_processed": summary.get("traces_processed", len(traces)),
        "total_llm_responses": len(responses),
        "detectors": det_stats,
        "llm_stats": llm_stats,
        "llm_telemetry": llm_telemetry,
        "anomaly_by_type": summary.get("anomaly_by_type", {}),
        "anomaly_by_severity": summary.get("anomaly_by_severity", {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+", help="artifact dirs (with-llm/)")
    ap.add_argument("--out", default=None, help="write JSON report here")
    args = ap.parse_args()

    results = {}
    for d in args.dirs:
        p = Path(d)
        label = p.parent.parent.parent.name  # FT-11b or FT-11d
        results[label] = score_dir(p)

    # Print summary
    for label, r in results.items():
        if "error" in r:
            print(f"{label}: {r['error']}")
            continue
        print(f"\n=== {label} ({r['traces_processed']} traces, {r['total_llm_responses']} LLM responses) ===")
        print(f"  chat_calls={r['llm_stats'].get('chat_calls')} embed_calls={r['llm_stats'].get('embed_calls')} "
              f"errors={r['llm_stats'].get('errors')} parse_rate={r['llm_stats'].get('json_parse_success',0)}/"
              f"{r['llm_stats'].get('json_parse_success',0)+r['llm_stats'].get('json_parse_fail',0)}")
        if r.get("llm_telemetry"):
            t = r["llm_telemetry"]
            print(f"  latency p50={t.get('latency_ms_p50')}ms p95={t.get('latency_ms_p95')}ms "
                  f"p99={t.get('latency_ms_p99')}ms tokens={t.get('total_tokens')} "
                  f"cache_hit_rate={t.get('cache_hit_rate')}")
        print(f"  per-detector:")
        for det, s in sorted(r["detectors"].items()):
            vp = s["llm_vs_pipeline"]
            print(f"    {det:25s} calls={s['total_calls']:4d} parse_rate={s['parse_rate']}% "
                  f"pos={s['positive_verdicts']:3d} neg={s['negative_verdicts']:3d} "
                  f"LLM-vs-pipeline: tp={vp['tp']} fp={vp['fp']} fn={vp['fn']} tn={vp['tn']}")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
