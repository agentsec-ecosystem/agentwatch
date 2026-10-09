ft_up_recorder
ft_assert_recorder "cca-consent" "python3 /ft/scripts/ingest-fixture.py --kind cca --corpus /ft/fixtures/cca"

ft_assert "cca-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_compliance_api.py
ft_capture_store_soft
ft_finalize
