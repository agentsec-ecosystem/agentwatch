ft_up_recorder
ft_start_daemon
ft_assert_recorder "env-delta" "python3 /ft/scripts/env_delta.py"
ft_assert "env-delta-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_environment_fingerprint.py
ft_capture_store_soft
ft_finalize
