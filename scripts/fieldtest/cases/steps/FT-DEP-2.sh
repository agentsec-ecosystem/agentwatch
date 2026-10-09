ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "attestation-config-changed" "python3 /ft/scripts/attestation_strip.py"
ft_capture_store
ft_finalize
