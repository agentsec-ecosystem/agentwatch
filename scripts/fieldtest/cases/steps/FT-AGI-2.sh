ft_up_recorder
ft_start_daemon
ft_assert_recorder "skill-answers" "python3 /ft/scripts/investigation_skill.py"
ft_assert "skill-contract" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_agent_interfaces.py
ft_capture_store_soft
ft_finalize
