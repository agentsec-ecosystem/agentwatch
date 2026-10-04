ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "session-present" "agentwatch sessions | grep -q ft04"
ft_capture_store
ft_finalize
