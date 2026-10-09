ft_up_recorder
ft_assert_recorder "hostile-contained" "python3 /ft/scripts/hostile-ingest.py --corpus /ft/fixtures/hostile"
ft_assert_recorder "quarantined" "test -s /data/agentwatch/quarantine.jsonl"
ft_capture_store_soft
ft_finalize
