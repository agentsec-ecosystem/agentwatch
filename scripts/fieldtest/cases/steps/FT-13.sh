ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_recorder bash -lc 'sed -i "3s/./X/" /data/agentwatch/records.jsonl'
ft_assert_recorder "tamper-detected" "! agentwatch verify-store"
ft_assert_recorder "repair" "agentwatch verify-store --repair --yes"
ft_assert_recorder "chain-green-after-repair" "agentwatch verify-store"
ft_assert_recorder "intact-prefix-kept" "grep -q '\"seq\": 0' /data/agentwatch/records.jsonl"
ft_assert_recorder "broken-record-dropped" "! grep -q '\"seq\": 1' /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
