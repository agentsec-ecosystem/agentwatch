ft_up_recorder
ft_start_daemon
ft_assert_recorder "capability-drift" "python3 /ft/scripts/capability-drift.py --kind drift"
ft_assert "capability-drift-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_capability_drift.py
ft_capture_store_soft
ft_finalize
