ft_up_recorder
ft_start_daemon
ft_emit --future
ft_assert_recorder "degraded-clock-skew" "curl -sf http://127.0.0.1:9100/healthz | grep -q clock-skew"
ft_capture_store
ft_finalize
