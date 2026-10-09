ft_up_recorder
ft_start_daemon
ft_assert_recorder "approval-fidelity" "python3 /ft/scripts/oversight-corpus.py --fidelity"
ft_assert "authorization-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_authorization.py
ft_capture_store_soft
ft_finalize
