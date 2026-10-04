ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "verify-privacy" "agentwatch verify-privacy"
ft_assert_recorder "no-api-key-leak" "! grep -q 'sk-abcdefghijklmnop' /data/agentwatch/records.jsonl"
ft_assert_recorder "no-card-leak" "! grep -q '4111 1111 1111 1111' /data/agentwatch/records.jsonl"
ft_assert_recorder "secret-detected" "grep -q secret-detected /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
