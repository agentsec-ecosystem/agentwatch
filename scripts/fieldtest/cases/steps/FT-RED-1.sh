ft_up_recorder
ft_start_daemon
ft_assert_recorder "redaction-benchmark" "agentwatch redact eval --json"
ft_assert "redact-eval-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_redact_eval.py
ft_capture_store_soft
ft_finalize
