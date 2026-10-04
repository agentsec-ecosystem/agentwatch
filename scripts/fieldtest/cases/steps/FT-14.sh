ft_up_recorder
ft_start_daemon
ft_emit --old
ft_recorder bash -lc 'kill -9 $(cat /data/agentwatch/daemon.pid) || true; rm -f /run/agentwatch/agentwatch.sock; sleep 1'
ft_start_daemon
ft_recorder bash -lc "sleep 3"
ft_assert_recorder "gap-record" "grep -q recording-gap /data/agentwatch/records.jsonl"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
