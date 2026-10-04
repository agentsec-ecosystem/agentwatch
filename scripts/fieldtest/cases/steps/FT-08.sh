ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "export-signed" "agentwatch checkpoint export --sign --output /tmp/cp.json && test -s /tmp/cp.json"
ft_assert_recorder "derive-pubkey" "python3 -c \"from agentwatch.signing import key_from_private; import pathlib; pathlib.Path('/tmp/cp.pub').write_bytes(key_from_private(pathlib.Path('/data/agentwatch/signing.key').read_bytes()).public_bytes)\""
ft_assert_recorder "verify-ok" "agentwatch checkpoint verify /tmp/cp.json --public-key /tmp/cp.pub --json | grep -q '\"ok\": true'"
ft_capture_store
ft_finalize
