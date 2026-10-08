ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "runner-segment" "python3 /ft/scripts/segment-runner.py"
ft_capture_store_soft
ft_finalize
