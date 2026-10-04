ft_up_recorder
ft_assert "llm-3way-validation" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces2":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics /ft/llm-validation.sh /traces/synthetic 25 /artifacts
ft_finalize
