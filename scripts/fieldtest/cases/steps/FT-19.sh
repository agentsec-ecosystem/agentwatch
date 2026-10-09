ft_record "compose up recorder jaeger otel-collector"
up_args=(-d); [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || up_args+=(--build)
"${STACK_COMPOSE[@]}" up "${up_args[@]}" recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
# Endpoint down must not break the agent (exit 0), then recover to a live endpoint.
ft_assert_recorder "endpoint-down-nonfatal" "python3 /ft/scripts/otel-probe.py --endpoint http://127.0.0.1:9 --service agentwatch"
ft_assert_recorder "recover" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
sleep 5
ft_assert_recorder "delivered-after-recovery" "curl -sf http://jaeger:16686/api/services | grep -q agentwatch"
ft_capture_store_soft
ft_finalize
