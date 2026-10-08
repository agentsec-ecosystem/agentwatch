ft_up_recorder
ft_start_daemon
ft_assert_recorder "index-rebuild-delete" "agentwatch index rebuild --json && agentwatch index drop --json && agentwatch sessions >/dev/null && agentwatch index rebuild --json"
ft_capture_store_soft
ft_finalize
