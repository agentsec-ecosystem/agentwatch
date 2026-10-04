ft_up_recorder
# Free memory: stop the long-running analytics worker before the heavy one-off run.
"${STACK_COMPOSE[@]}" stop analytics >/dev/null 2>&1 || true
ft_assert "full-corpus-validate" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed shard '' /artifacts
ft_finalize
