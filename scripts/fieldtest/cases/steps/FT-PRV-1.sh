ft_up_recorder
ft_start_daemon
ft_assert_recorder "commit-to-session" "python3 /ft/scripts/provenance-repo.py --commit-to-session"
ft_assert "provenance-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_provenance.py
ft_capture_store_soft
ft_finalize
