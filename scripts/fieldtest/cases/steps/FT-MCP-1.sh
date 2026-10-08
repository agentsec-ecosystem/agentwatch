ft_up_recorder
ft_assert_recorder "mcp-surface" "python3 /ft/scripts/ingest-fixture.py --kind mcp --corpus /ft/fixtures/mcp && agentwatch verify-store"
ft_capture_store_soft
ft_finalize
