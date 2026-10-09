ft_up_recorder
ft_start_daemon
ft_assert_recorder "pg-down-commands" "agentwatch sessions >/dev/null && agentwatch verify-store"
ft_assert_recorder "index-rebuild-bitfor-bit" "python3 /ft/scripts/pg_rebuild.py"
ft_capture_store_soft
ft_finalize
