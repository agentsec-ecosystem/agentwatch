ft_up_recorder
ft_assert_recorder "acs-ingest" "python3 /ft/scripts/ingest-fixture.py --kind acs --corpus /ft/fixtures/acs && agentwatch verify-store"
ft_assert "acs-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_acs_ingest.py
ft_capture_store_soft
ft_finalize
