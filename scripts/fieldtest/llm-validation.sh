#!/usr/bin/env bash
# 3-way LLM detector validation on the in-repo corpus (M23 FT-11b / FT-11d).
#
# Usage:
#   docker compose ... run --rm --entrypoint bash \
#     -v "$CORPUS":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts \
#     -e OMLX_MODEL=... analytics /ft/scripts/llm-validation.sh /traces/processed 25 [outdir]
# Writes summaries + llm_responses.json under $OUT so LLM requests/responses and
# per-detector results are captured for inspection.
set -euo pipefail

INPUT="${1:-/traces/processed}"
TRACES="${2:-25}"
OUT="${3:-/artifacts}"
MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}"
if ! mkdir -p "$OUT" 2>/dev/null; then OUT=/tmp; mkdir -p "$OUT"; fi

if [[ ! -d "$INPUT" ]]; then
  echo "corpus input directory not found: $INPUT" >&2
  exit 1
fi

echo "== llm-validation: pass 1 (no LLM) over $TRACES traces from $INPUT; out=$OUT =="
python -m analytics.main validate --input "$INPUT" --output "$OUT/no-llm" --max-traces "$TRACES" --db

echo "== llm-validation: pass 2 (LLM ${MODEL}) =="
ANALYTICS_LLM_CHAT_MODEL="$MODEL" \
  python -m analytics.main validate --input "$INPUT" --output "$OUT/llm" --max-traces "$TRACES" \
    --llm-sample "$TRACES" --llm-batch 10 --db

echo "== llm-validation: asserting LLM-only detectors fired =="
python - "$OUT" <<'PY'
import glob, json, os, sys
out = sys.argv[1]
LLM_ONLY = {"semantic_loop", "hallucination", "goal_drift", "quality_degradation",
            "confusion_pattern", "output_drift"}

def load(pattern):
    matches = glob.glob(pattern, recursive=True)
    return json.load(open(matches[0])) if matches else {}

llm = load(f"{out}/llm/**/summary.json")
fired = set(llm.get("anomaly_by_type", {}))
llm_only = fired & LLM_ONLY
# Capture evidence of actual LLM requests/responses.
resp_files = glob.glob(f"{out}/llm/**/llm_responses.json", recursive=True)
resp_count = 0
for f in resp_files:
    try:
        resp_count += json.load(open(f)).get("total_responses", 0)
    except (OSError, ValueError):
        pass
print(f"llm-validation: llm types={len(fired)} llm-only fired={sorted(llm_only)} "
      f"llm_responses={resp_count}")
if not llm.get("traces_processed"):
    print("LLM pass processed no traces", file=sys.stderr); sys.exit(1)
if not llm_only:
    print("no LLM-only detector fired", file=sys.stderr); sys.exit(1)
if resp_count == 0:
    print("no LLM requests/responses captured", file=sys.stderr); sys.exit(1)
PY
