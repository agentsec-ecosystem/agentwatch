ft_up_recorder
ft_start_daemon
ft_assert_recorder "self-test-in-health" "curl -sf http://127.0.0.1:9100/healthz | grep -q self_test_passing"
ft_finalize
