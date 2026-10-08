ft_up_recorder
ft_start_daemon
ft_assert_recorder "telemetry-off-default" "agentwatch coverage --json"
ft_assert_recorder "telemetry-module" "python3 -c "import agentwatch.detector_telemetry""
ft_capture_store_soft
ft_finalize
