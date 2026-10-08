ft_up_recorder
ft_start_daemon
ft_assert "xht-replay-self-test" bash -lc "python3 /ft/scripts/xht_replay.py --self-test"
ft_capture_store_soft
ft_finalize
