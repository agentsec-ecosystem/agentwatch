ft_up_recorder
ft_assert_recorder "grpc-stream" "python3 /ft/scripts/otel_grpc_stream.py --endpoint http://otel-grpc:4317 --mb 100"
ft_capture_store_soft
ft_finalize
