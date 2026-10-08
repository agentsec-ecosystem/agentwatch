ft_up_recorder
ft_start_daemon
ft_assert_recorder "doctor-managed" "agentwatch doctor --json | grep -Eq 'hooks effective: (yes|blocked|unknown)'"
ft_assert_recorder "never-installed-when-blocked" "! agentwatch doctor | grep -q 'installed' || agentwatch doctor | grep -q 'effective'"
ft_capture_store_soft
ft_finalize
