ft_up_recorder
ft_start_daemon
ft_assert_recorder "stream-drop-reconcile" "python3 /ft/scripts/stream-probe.py --mode drop-consumer --bounded"
ft_capture_store_soft
ft_finalize
