ft_up_recorder
ft_start_daemon
ft_assert "claims-ledger" bash -lc "test -f $REPO_ROOT/docs/release/claims-ledger.json || test -f $REPO_ROOT/reference/known-limitations.md"
ft_capture_store_soft
ft_finalize
