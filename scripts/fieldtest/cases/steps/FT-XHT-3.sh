ft_up_recorder
ft_start_daemon
ft_assert "xht-cross-parser" bash -lc "python3 /ft/scripts/xht_replay.py --cross-parser"
ft_capture_store_soft
ft_finalize
