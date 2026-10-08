ft_up_recorder
ft_assert_recorder "aat-ingest" "agentwatch ingest --format aat /ft/fixtures/aat/foreign.aat.json"
ft_assert_recorder "quarantine" "test -s /data/agentwatch/quarantine.jsonl"
ft_capture_store_soft
ft_finalize
