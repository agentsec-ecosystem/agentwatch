ft_up_recorder
for mode in metadata-only truncated hashed full; do
  d="/data/agentwatch-$mode"
  ft_recorder bash -lc "AGENTWATCH_STORE__PATH=$d AGENTWATCH_PRIVACY__MODE=$mode AGENTWATCH_SOCKET=/run/agentwatch/$mode.sock agentwatch-daemon >/tmp/daemon-$mode.log 2>&1 & for i in \$(seq 1 50); do [ -S /run/agentwatch/$mode.sock ] && break; sleep 0.2; done"
  ft_recorder bash -lc "AGENTWATCH_SOCKET=/run/agentwatch/$mode.sock python3 /ft/scripts/emit-hook.py --corpus secrets" || true
  ft_assert_recorder "mode-$mode" "grep -q '\"privacy_mode\": \"$mode\"' $d/records.jsonl"
  ft_recorder bash -lc "pkill -f agentwatch-daemon || true; sleep 0.3"
done
ft_capture_store_soft
ft_finalize
