ft_up_recorder
ft_start_daemon
ft_assert "second-corpus" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed 2000  /artifacts
ft_capture_store_soft
ft_finalize
