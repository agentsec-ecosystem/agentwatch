ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "replay" "agentwatch replay ft04 | grep -q Bash"
ft_capture_store
ft_finalize
