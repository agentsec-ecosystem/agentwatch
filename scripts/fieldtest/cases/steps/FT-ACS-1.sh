ft_up_recorder
ft_assert_recorder "acs-ingest" "python3 /ft/scripts/ingest-fixture.py --kind acs --corpus /ft/fixtures/acs && agentwatch verify-store"
ft_capture_store_soft
ft_finalize
