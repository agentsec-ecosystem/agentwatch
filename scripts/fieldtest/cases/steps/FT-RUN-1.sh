ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "runner-segment" "python3 /ft/scripts/segment-runner.py"
ft_assert "runner-segment-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_runner_segments.py
ft_capture_store_soft
ft_finalize
