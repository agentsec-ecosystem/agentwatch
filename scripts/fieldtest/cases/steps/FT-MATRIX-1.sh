ft_up_recorder
ft_start_daemon
ft_assert "matrix-file" bash -lc "test -f $REPO_ROOT/docs/reference/compatibility.md"
ft_assert "matrix-honest-tiers" bash -lc "grep -qE 'live-verified|fixture-verified' $REPO_ROOT/docs/reference/compatibility.md"
ft_capture_store_soft
ft_finalize
