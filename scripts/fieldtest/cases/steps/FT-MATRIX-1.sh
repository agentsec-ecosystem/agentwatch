ft_up_recorder
ft_start_daemon
ft_assert "matrix-file" bash -lc "test -f $REPO_ROOT/docs/reference/compatibility.md"
ft_assert "no-modeled-tier1" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 "$REPO_ROOT/scripts/fieldtest/check-matrix-tiers.py"
ft_capture_store_soft
ft_finalize
