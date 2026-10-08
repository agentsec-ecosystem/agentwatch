ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "privacy-default" "grep -q '"privacy_mode": "metadata-only"' /data/agentwatch/records.jsonl"
ft_assert_recorder "privacy-property" "python3 /ft/scripts/privacy_property.py"
ft_capture_store
ft_finalize
