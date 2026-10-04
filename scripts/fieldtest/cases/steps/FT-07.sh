ft_up_recorder
ft_assert_recorder "demo" "agentwatch demo --json >/dev/null"
ft_assert_recorder "purge" "agentwatch demo --purge --json >/dev/null"
ft_capture_store
ft_finalize
