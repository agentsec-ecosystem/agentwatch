ft_up_recorder
ft_start_daemon
ft_assert_recorder "detector-telemetry-off-default" "agentwatch detector status --json | grep -q '"enabled": false' || python3 -c 'import agentwatch.detector_telemetry'"
ft_capture_store_soft
ft_finalize
