ft_up_recorder
ft_start_daemon
ft_assert_recorder "permission-mode" "python3 /ft/scripts/oversight-corpus.py --modes"
ft_assert "oversight-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_oversight.py
ft_capture_store_soft
ft_finalize
