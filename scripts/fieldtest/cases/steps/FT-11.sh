ft_up_recorder
ft_start_daemon
ft_assert_recorder "drive-agent" "python3 /ft/scripts/drive-agent.py --session ft-llm"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "records" "agentwatch sessions | grep -q ft-llm"
ft_assert_recorder "llm-io-captured" "test -s /data/agentwatch/test-llm-io.jsonl"
ft_assert_recorder "llm-response-captured" "grep -q '\"response\"' /data/agentwatch/test-llm-io.jsonl"
ft_capture_store
ft_finalize
