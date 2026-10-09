ft_up_recorder
ft_start_daemon
ft_assert "codemod" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" "$REPO_ROOT"/tests/test_codemod_*.py packages/python-sdk/tests/test_conformance_runner.py
ft_capture_store_soft
ft_finalize
