ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "siem-conformance" "python3 /ft/scripts/siem_conformance.py"
ft_assert "siem-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_siem_consumers.py packages/python-sdk/tests/test_siem_syslog.py
ft_capture_store_soft
ft_finalize
