ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "coverage-attestation" "agentwatch coverage --json | grep -q attestation"
ft_capture_store
ft_finalize
