ft_up_recorder
ft_start_daemon
ft_assert_recorder "sandbox-events" "python3 /ft/scripts/oversight-corpus.py --sandbox"
ft_assert "sandbox-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_sandbox_events.py
ft_capture_store_soft
ft_finalize
