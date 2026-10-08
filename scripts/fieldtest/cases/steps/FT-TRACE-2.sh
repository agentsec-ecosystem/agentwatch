ft_up_recorder
ft_start_daemon
ft_assert "fleet-skew" bash -lc "python3 /ft/scripts/fleet-run.py --skew 3 --hosts fleet-h1,fleet-h2"
ft_capture_store_soft
ft_finalize
