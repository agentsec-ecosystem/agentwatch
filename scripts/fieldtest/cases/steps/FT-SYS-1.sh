ft_up_recorder
ft_start_daemon
ft_assert_recorder "system-ingest" "python3 /ft/scripts/ingest-fixture.py --kind system"
ft_assert "system-ingest-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_system_ingest.py
ft_capture_store_soft
ft_finalize
