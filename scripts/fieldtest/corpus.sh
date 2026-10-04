#!/usr/bin/env bash
# Corpus detector validation (M23 FT-06b / FT-15b / FT-15c) — runs INSIDE the
# analytics image against the in-repo processed-trace corpus.
#
# Usage:
#   docker compose ... run --rm --entrypoint bash \
#     -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft \
#     -v "$FT_CASE_DIR/artifacts":/artifacts \
#     analytics /ft/scripts/corpus.sh /traces/processed <max|0=all> [--diagnose] [outdir]
# Outputs (summary.json, diagnostics) are written under $OUT so the artifacts
# volume captures them for inspection.
set -euo pipefail

INPUT="${1:-/traces/processed}"
MAX_TRACES="${2:-2000}"
DIAGNOSE="${3:-}"
OUT="${4:-/artifacts}"
if ! mkdir -p "$OUT" 2>/dev/null; then OUT=/tmp; mkdir -p "$OUT"; fi

if [[ ! -d "$INPUT" ]]; then
  echo "corpus input directory not found: $INPUT" >&2
  exit 1
fi
files="$(find "$INPUT" -name '*.parquet' | wc -l | tr -d ' ')"
if [[ "$files" -eq 0 ]]; then
  echo "no parquet traces under $INPUT (generate the corpus first)" >&2
  exit 1
fi
echo "== corpus: $files parquet files under $INPUT; validating ${MAX_TRACES:-all} traces; out=$OUT =="

if [[ "$MAX_TRACES" == "shard" ]]; then
  # Full corpus in per-dataset shards (bounds memory; the single-pass full run OOMs).
  processed_total=0
  shards=0
  for dataset_dir in "$INPUT"/*/; do
    [[ -d "$dataset_dir" ]] || continue
    name="$(basename "$dataset_dir")"
    python -m analytics.main validate --input "$dataset_dir" --output "$OUT/validation/$name" --max-files 5 >/dev/null
    shards=$((shards + 1))
  done
  python - "$OUT" "$shards" <<'PY'
import glob, json, sys
out, shards = sys.argv[1], int(sys.argv[2])
summaries = glob.glob(f"{out}/validation/**/summary.json", recursive=True)
processed = sum(json.load(open(s)).get("traces_processed", 0) for s in summaries)
if shards == 0 or not summaries or processed == 0:
    print(f"sharded full-corpus incomplete: shards={shards} summaries={len(summaries)} processed={processed}", file=sys.stderr)
    sys.exit(1)
print(f"corpus: sharded full-corpus validated {processed} traces across {shards} datasets")
PY
  exit $?
fi

if [[ "${MAX_TRACES:-0}" -gt 0 ]]; then
  python -m analytics.main validate --input "$INPUT" --output "$OUT/validation" --max-traces "$MAX_TRACES"
else
  python -m analytics.main validate --input "$INPUT" --output "$OUT/validation"
fi

python - "$OUT" <<'PY'
import glob, json, sys
out = sys.argv[1]
matches = glob.glob(f"{out}/validation/**/summary.json", recursive=True)
if not matches:
    print("no summary.json produced", file=sys.stderr); sys.exit(1)
summary = json.load(open(matches[0]))
processed = summary.get("traces_processed", 0)
if not processed:
    print(f"traces_processed is zero: {summary}", file=sys.stderr); sys.exit(1)
print(f"corpus: validated {processed} traces, anomalies={summary.get('anomaly_count', 0)}")
PY

if [[ "$DIAGNOSE" == "--diagnose" ]]; then
  echo "== corpus: compatibility diagnostic =="
  python -m analytics.main validate --input "$INPUT" --output "$OUT/diagnose" --max-traces "$MAX_TRACES" --diagnose
  python - "$OUT" <<'PY'
import glob, json, sys
out = sys.argv[1]
matches = glob.glob(f"{out}/diagnose/**/compatibility_matrix.json", recursive=True)
if not matches:
    print("no compatibility_matrix.json produced", file=sys.stderr); sys.exit(1)
matrix = json.load(open(matches[0]))
if not matrix:
    print("compatibility matrix is empty", file=sys.stderr); sys.exit(1)
print(f"corpus: compatibility matrix entries={len(matrix)}")
PY
fi
