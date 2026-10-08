ft_up_recorder
ft_assert_recorder "gateway-ingest" "python3 /ft/scripts/ingest-fixture.py --kind gateway --corpus /ft/fixtures/gateway"
ft_assert_recorder "cost-exact-vs-estimated" "agentwatch cost --json | grep -Eq 'exact|estimated'"
ft_capture_store_soft
ft_finalize
