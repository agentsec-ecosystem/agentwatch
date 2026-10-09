ft_up_recorder
ft_start_daemon
ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json
ft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"
ft_assert "detector-catalog-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" services/analytics/tests/test_detector_catalog.py
ft_capture_store_soft
ft_finalize
