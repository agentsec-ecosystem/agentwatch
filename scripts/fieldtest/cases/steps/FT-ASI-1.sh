ft_up_recorder
ft_start_daemon
ft_assert_recorder "asi-report" "agentwatch compliance report --framework owasp-asi-2026 --out /tmp/asi"
ft_assert "asi-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_compliance_asi.py
ft_capture_store_soft
ft_finalize
