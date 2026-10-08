ft_up_recorder
ft_start_daemon
ft_assert_recorder "retention-apply" "agentwatch retention apply --profile general-6mo"
ft_assert_recorder "signed-default" "python3 /ft/scripts/signed_default.py"
ft_capture_store_soft
ft_finalize
