ft_up_recorder
ft_start_daemon
ft_assert "openapi-present" bash -lc "curl -sf http://localhost:8100/openapi.json >/dev/null"
ft_capture_store_soft
ft_finalize
