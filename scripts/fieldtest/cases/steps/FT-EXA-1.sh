ft_up_recorder
ft_start_daemon
ft_assert "examples-gallery" bash -lc "python3 -c 'import pathlib; assert list(pathlib.Path("$REPO_ROOT/examples").glob("**/*.py"))'"
ft_capture_store_soft
ft_finalize
