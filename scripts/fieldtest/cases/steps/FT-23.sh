ft_up_recorder
ft_start_daemon
ft_emit --corpus partial --session ft-partial
ft_assert_recorder "replay" "agentwatch replay ft-partial | grep -q Bash"
ft_assert_recorder "sessions" "agentwatch sessions | grep -q ft-partial"
ft_capture_store
ft_finalize
