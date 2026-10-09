ft_up_recorder
ft_start_daemon
ft_assert_recorder "incident-case" "python3 /ft/scripts/case_incident.py"
ft_assert "incident-case-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_incident_cases.py
ft_capture_store_soft
ft_finalize
