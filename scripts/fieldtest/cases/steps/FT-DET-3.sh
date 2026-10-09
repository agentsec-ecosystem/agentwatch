ft_up_recorder
ft_start_daemon
ft_assert "detector-matrix-llm" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics -m analytics.scenario_validation --all
ft_assert "llm-detectors-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" services/analytics/tests/test_llm_eval.py services/analytics/tests/test_llm_detectors.py
ft_capture_store_soft
ft_finalize
