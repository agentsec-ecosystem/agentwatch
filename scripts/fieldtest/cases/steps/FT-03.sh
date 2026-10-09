ft_record "compose up recorder jaeger otel-collector"
up_args=(-d); [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || up_args+=(--build)
"${STACK_COMPOSE[@]}" up "${up_args[@]}" recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
sleep 5
ft_assert_recorder "jaeger-services" "curl -sf http://jaeger:16686/api/services | grep -q agentwatch"
ft_capture_store_soft
ft_finalize
