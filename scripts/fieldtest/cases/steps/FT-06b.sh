ft_up_recorder
ft_assert "corpus-validate" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed 2000 '' /artifacts
ft_finalize
