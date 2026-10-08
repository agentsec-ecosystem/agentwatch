ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "privacy-default" "grep -q '"privacy_mode": "truncated"' /data/agentwatch/records.jsonl"
ft_assert_recorder "no-content-metadata" "python3 /ft/scripts/privacy_property.py"
ft_capture_store
ft_finalize
