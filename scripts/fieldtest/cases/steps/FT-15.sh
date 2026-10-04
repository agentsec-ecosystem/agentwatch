ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
sleep 5
ft_assert "anomalies-api" bash -lc "curl -sf http://localhost:8100/api/v1/anomalies -o '$FT_CASE_DIR/artifacts/anomalies.json' && python3 -c \"import json; d=json.load(open('$FT_CASE_DIR/artifacts/anomalies.json')); assert d['data']['items']\""
# Full detector matrix: all 154 ported scenarios across all 35 rule-based
# detectors (positive must fire, negative must not, escalated = critical).
mkdir -p "$FT_CASE_DIR/artifacts"
ft_assert "detector-full-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json
ft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"
ft_finalize
