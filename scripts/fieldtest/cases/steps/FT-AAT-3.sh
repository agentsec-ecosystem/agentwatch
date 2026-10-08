ft_up_recorder
ft_start_daemon
ft_assert_recorder "aat-version-cited" "agentwatch --version | grep -qi aat"
ft_assert_recorder "aat-drift" "python3 /ft/scripts/aat_drift.py"
ft_capture_store_soft
ft_finalize
