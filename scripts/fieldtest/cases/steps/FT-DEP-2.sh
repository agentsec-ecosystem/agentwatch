ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "recorder-config-changed" "grep -q recorder-config-changed /data/agentwatch/records.jsonl"
ft_assert_recorder "attestation" "agentwatch coverage --json | grep -q attestation"
ft_capture_store
ft_finalize
