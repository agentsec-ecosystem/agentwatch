ft_up_recorder
ft_recorder bash -lc 'AGENTWATCH_STORE__MAX_SIZE_MB=1 agentwatch-daemon >/tmp/daemon.log 2>&1 & for i in $(seq 1 50); do [ -S "$AGENTWATCH_SOCKET" ] && break; sleep 0.2; done'
ft_recorder python3 /ft/scripts/run-soak.py --count 6000 --interval 0.001 || true
ft_assert_recorder "stopped-and-surfaced" "agentwatch status | grep -qi stopped"
ft_capture_store
ft_finalize
