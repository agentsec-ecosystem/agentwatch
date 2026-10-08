ft_up_recorder
ft_start_daemon
ft_assert "detector-matrix-llm" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics -m analytics.scenario_validation --all --llm
ft_capture_store_soft
ft_finalize
