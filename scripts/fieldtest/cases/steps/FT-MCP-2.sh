ft_up_recorder
ft_assert_recorder "mcp-malformed-quarantine" "python3 /ft/scripts/ingest-fixture.py --kind mcp-malformed && test -s /data/agentwatch/quarantine.jsonl"
ft_capture_store_soft
ft_finalize
