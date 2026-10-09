ft_up_recorder
ft_start_daemon
ft_assert "openapi-present" bash -lc "curl -sf http://localhost:8100/openapi.json >/dev/null"
ft_assert "openapi-contract" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" services/api/tests/test_openapi_contract.py
ft_capture_store_soft
ft_finalize
