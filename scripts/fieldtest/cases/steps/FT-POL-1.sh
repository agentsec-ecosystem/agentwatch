ft_up_recorder
ft_start_daemon
ft_assert_recorder "suggest-policy-no-write" "cd /tmp && rm -f proposed.json && agentwatch suggest-policy --since 30d --target claude-settings --out /tmp/proposed.json && test -s /tmp/proposed.json"
ft_assert_recorder "what-if" "agentwatch what-if /tmp/proposed.json --since 30d --json"
ft_capture_store_soft
ft_finalize
