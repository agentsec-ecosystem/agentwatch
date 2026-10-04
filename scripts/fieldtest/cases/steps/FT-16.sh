ft_up_recorder
ft_recorder bash -lc 'rm -f /run/agentwatch/agentwatch.sock.spool || true'
# The daemon is deliberately NOT running: emit-hook spools instead of dropping (F1).
ft_emit --corpus secrets
ft_assert_recorder "spooled" "test -s /run/agentwatch/agentwatch.sock.spool"
ft_start_daemon
sleep 2
ft_assert_recorder "replayed-once" "agentwatch verify-store && agentwatch sessions | grep -q ft04"
ft_capture_store
ft_finalize
