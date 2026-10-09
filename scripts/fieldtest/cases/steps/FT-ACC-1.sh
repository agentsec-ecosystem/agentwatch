ft_up_recorder
ft_start_daemon
ft_assert_recorder "role-matrix" "python3 /ft/scripts/governance_matrix.py --roles"
ft_assert "access-model-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_access.py
ft_capture_store_soft
ft_finalize
