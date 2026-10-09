ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "digest-derived" "python3 /ft/scripts/digest_check.py"
ft_capture_store_soft
ft_finalize
