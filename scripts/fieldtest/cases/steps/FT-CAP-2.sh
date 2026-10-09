ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "capability-load-attribution" "python3 /ft/scripts/capability-drift.py --kind load"
ft_capture_store_soft
ft_finalize
