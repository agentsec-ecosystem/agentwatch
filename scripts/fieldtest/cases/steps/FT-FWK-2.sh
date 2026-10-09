ft_up_recorder
ft_start_daemon
ft_assert_recorder "instrument-detect" "python3 /ft/scripts/instrument_detect.py"
ft_assert "instrument-detect-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_autoinstrument.py
ft_capture_store_soft
ft_finalize
