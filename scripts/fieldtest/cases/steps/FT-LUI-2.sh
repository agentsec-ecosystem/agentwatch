ft_up_recorder
ft_start_daemon
ft_assert_recorder "index-rebuild-delete" "agentwatch index --rebuild >/dev/null && rm -rf /data/agentwatch/index && agentwatch sessions >/dev/null && agentwatch index --rebuild >/dev/null"
ft_capture_store_soft
ft_finalize
