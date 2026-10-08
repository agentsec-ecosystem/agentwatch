ft_assert "verifier-artifact" bash -lc "test -f $REPO_ROOT/docs/release/verifier/agentwatch-verify.html"
ft_assert "verifier-checksum" bash -lc "cd $REPO_ROOT && python3 scripts/build_browser_verifier.py --check"
ft_finalize
