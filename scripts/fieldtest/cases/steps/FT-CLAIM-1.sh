ft_up_recorder
ft_start_daemon
ft_assert "claims-ledger-json" python3 -m json.tool "$REPO_ROOT/docs/release/claims-ledger.json"
ft_assert "known-limitations" test -f "$REPO_ROOT/docs/reference/known-limitations.md"
ft_capture_store_soft
ft_finalize
