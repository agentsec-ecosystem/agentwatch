ft_up_recorder
ft_assert_recorder "gemini-ingest" "python3 /ft/scripts/ingest-fixture.py --kind gemini --corpus /ft/fixtures/gemini && agentwatch verify-store"
ft_capture_store_soft
ft_finalize
