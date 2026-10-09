ft_up_recorder
ft_assert_recorder "gateway-ingest" "python3 /ft/scripts/ingest-fixture.py --kind gateway --corpus /ft/fixtures/gateway"
ft_assert_recorder "cost-exact-vs-estimated" "agentwatch cost --json | grep -Eq 'exact|estimated'"
ft_assert "gateway-cost-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_gateway_cost.py
ft_capture_store_soft
ft_finalize
