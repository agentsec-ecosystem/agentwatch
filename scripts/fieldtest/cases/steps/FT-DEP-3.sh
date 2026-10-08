ft_up_recorder
ft_start_daemon
ft_assert_recorder "hook-perf-gate" "python3 /ft/scripts/run-soak.py --count 500 --interval 0.002 --min-delivery 1.0"
ft_capture_store_soft
ft_finalize
