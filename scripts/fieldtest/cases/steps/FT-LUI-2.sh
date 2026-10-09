ft_up_recorder
ft_start_daemon
ft_assert_recorder "index-rebuild-delete" "agentwatch index rebuild --json && agentwatch index drop --json && agentwatch sessions >/dev/null && agentwatch index rebuild --json"

ft_assert "index-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_query_index.py packages/python-sdk/tests/test_purge_propagation.py
ft_capture_store_soft
ft_finalize
