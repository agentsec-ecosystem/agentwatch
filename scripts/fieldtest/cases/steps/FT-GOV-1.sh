ft_up_recorder
ft_start_daemon
ft_assert "codemod" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" tests/test_codemod_agent_exec_trace.py packages/python-sdk/tests/test_conformance_runner.py
ft_capture_store_soft
ft_finalize
