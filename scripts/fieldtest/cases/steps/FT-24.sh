ft_up_recorder
ft_start_daemon
ft_assert_recorder "states-recording" "curl -sf http://127.0.0.1:9100/healthz | grep -q '\"state\": \"recording\"'"
ft_assert_recorder "status-matches" "agentwatch status | grep -q 'state: recording'"
ft_capture_store
ft_finalize
