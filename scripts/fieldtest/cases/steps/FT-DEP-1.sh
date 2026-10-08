ft_up_recorder
ft_start_daemon
ft_assert_recorder "doctor-effective" "agentwatch doctor | grep -Eq 'hooks effective: (yes|blocked|unknown|no)'"
ft_capture_store_soft
ft_finalize
