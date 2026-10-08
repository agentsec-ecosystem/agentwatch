ft_up_recorder
ft_start_daemon
ft_assert "examples-gallery" test -n "$(find "$REPO_ROOT/examples" -name "*.py" -print -quit)"
ft_capture_store_soft
ft_finalize
