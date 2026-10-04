ft_up_recorder
ft_recorder python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl
ft_assert_recorder "purge" "agentwatch purge ft-seed-main --reason 'subject request' --yes"
ft_assert_recorder "chain-green" "agentwatch verify-store"
ft_assert_recorder "marker-present" "grep -q session-purge /data/agentwatch/records.jsonl"
ft_assert_recorder "tombstoned" "grep -q '\"tombstone\": true' /data/agentwatch/records.jsonl"
ft_assert_recorder "payload-gone" "! grep -q 'make build' /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
