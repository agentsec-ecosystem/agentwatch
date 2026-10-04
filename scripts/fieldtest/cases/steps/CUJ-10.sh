ft_up_recorder
ft_recorder python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl --out /tmp/ft-fixtures
ft_assert_recorder "cli" "agentwatch cost --by project >/dev/null"

ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
