ft_up_recorder
ft_start_daemon
ft_assert_recorder "memory-oob-edit" "python3 /ft/scripts/capability-drift.py --kind memory"
ft_assert "memory-capability-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_memory_capability.py packages/python-sdk/tests/test_memory_surface.py
ft_capture_store_soft
ft_finalize
