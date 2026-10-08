ft_up_recorder
ft_assert_recorder "codex-rollout" "python3 /ft/scripts/ingest-fixture.py --kind codex --corpus /ft/fixtures/codex && agentwatch verify-store"
ft_capture_store_soft
ft_finalize
