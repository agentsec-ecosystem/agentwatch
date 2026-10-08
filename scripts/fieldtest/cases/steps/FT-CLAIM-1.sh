ft_up_recorder
ft_start_daemon
ft_assert "claims-ledger" bash -lc "test -f $REPO_ROOT/docs/release/claims-ledger.json"
ft_assert "known-limitations" bash -lc "test -f $REPO_ROOT/docs/reference/known-limitations.md"
ft_capture_store_soft
ft_finalize
