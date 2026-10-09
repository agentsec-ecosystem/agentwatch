ft_up_recorder
ft_start_daemon
ft_assert_recorder "compliance-report" "agentwatch compliance report --framework iso-42001 --period Q3-2026 --out /tmp/audit"
ft_assert "compliance-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_compliance.py packages/python-sdk/tests/test_compliance_docs.py
ft_capture_store_soft
ft_finalize
