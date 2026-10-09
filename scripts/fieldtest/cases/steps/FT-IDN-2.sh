ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "identity-no-secrets" "python3 /ft/scripts/privacy_property.py --what identity"
ft_capture_store
ft_finalize
