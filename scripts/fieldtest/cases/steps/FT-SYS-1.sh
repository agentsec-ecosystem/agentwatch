ft_up_recorder
ft_start_daemon
ft_assert_recorder "system-ingest" "python3 /ft/scripts/ingest-fixture.py --kind system"
ft_capture_store_soft
ft_finalize
