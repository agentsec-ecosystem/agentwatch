ft_up_recorder
ft_start_daemon
ft_assert_recorder "outcomes" "agentwatch outcomes --since 30d --by project --json | grep -Eq 'numerator|denominator'"
ft_capture_store_soft
ft_finalize
