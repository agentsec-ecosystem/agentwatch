ft_up_recorder
ft_assert_recorder "cursor-corpus" "python3 /ft/scripts/ingest-fixture.py --kind cursor --corpus /ft/fixtures/cursor"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store_soft
ft_finalize
