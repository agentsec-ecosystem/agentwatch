ft_up_recorder
ft_assert "cross-framework-raw-agent" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT":/src -w /src -e OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 recorder -lc "python m13-agents/agent-raw/generate_traces.py"
sleep 5
ft_assert_recorder "cross-framework-visible" "curl -sf http://jaeger:16686/api/services | grep -q m13-raw-agent"
ft_finalize
