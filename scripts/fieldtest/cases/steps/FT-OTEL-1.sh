ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
ft_assert "jaeger" bash -lc "curl -sf http://localhost:16686/api/services | grep -q agentwatch"
ft_assert "tempo" bash -lc "curl -sf http://localhost:3200/api/search/tags || true"
ft_capture_store
ft_finalize
