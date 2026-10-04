ft_up_recorder
ft_start_daemon
ft_assert_recorder "soak" "python3 /ft/scripts/run-soak.py --count 10000 --interval 0.01 --min-delivery 0.99"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
