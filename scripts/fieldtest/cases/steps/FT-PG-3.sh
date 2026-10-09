ft_up_recorder
ft_start_daemon
ft_assert_recorder "sdk-in-store" "python3 /ft/scripts/sdk_emit.py && agentwatch verify-store"
ft_assert_recorder "union-fallback" "agentwatch union --json"
ft_capture_store_soft
ft_finalize
