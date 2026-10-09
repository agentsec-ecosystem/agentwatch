ft_up_recorder
ft_start_daemon
ft_assert_recorder "oversight-report" "python3 /ft/scripts/oversight-corpus.py --report"
ft_assert "permission-mode-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_permission_mode.py
ft_capture_store_soft
ft_finalize
