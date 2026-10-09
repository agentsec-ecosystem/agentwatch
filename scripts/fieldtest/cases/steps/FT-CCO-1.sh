ft_up_recorder
ft_assert_recorder "native-otel-join" "python3 /ft/scripts/native-otel-join.py --corpus /ft/fixtures/cco"
ft_assert "otel-join-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_claude_otel.py
ft_capture_store_soft
ft_finalize
