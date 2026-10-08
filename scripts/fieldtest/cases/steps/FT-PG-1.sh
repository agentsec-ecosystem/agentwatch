ft_up_recorder
ft_start_daemon
ft_assert_recorder "pg-down-commands" "agentwatch sessions >/dev/null && agentwatch verify-store"
ft_assert_recorder "index-rebuild" "agentwatch index rebuild --json && agentwatch index rebuild --json"
ft_capture_store_soft
ft_finalize
