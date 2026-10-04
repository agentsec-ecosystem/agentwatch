ft_up_recorder
ft_start_daemon
ft_assert_recorder "soak" "python3 /ft/scripts/run-soak.py --count 500 --interval 0.002 --min-delivery 1.0"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
