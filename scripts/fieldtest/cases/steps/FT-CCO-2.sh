ft_up_recorder
ft_assert_recorder "agent-sdk-native" "python3 /ft/scripts/ingest-fixture.py --kind cco"
ft_assert "agent-sdk-native-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_claude_agent_sdk.py
ft_capture_store_soft
ft_finalize
