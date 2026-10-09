ft_up_recorder
ft_start_daemon
ft_assert_recorder "concurrency-report" "python3 /ft/scripts/concurrency_probe.py"
ft_assert "concurrency-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_concurrency.py
ft_capture_store_soft
ft_finalize
