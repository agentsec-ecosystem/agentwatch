ft_up_recorder
ft_start_daemon
ft_assert_recorder "stream-p99" "python3 /ft/scripts/stream-probe.py --mode p99 --budget-ms 1000"
ft_capture_store_soft
ft_finalize
