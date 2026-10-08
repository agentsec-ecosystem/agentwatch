ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "aat-export" "agentwatch export-session ft04 --format aat --out /tmp/s.aat.json && test -s /tmp/s.aat.json"
ft_assert_recorder "aat-external-consumer" "python3 /ft/scripts/aat_roundtrip.py /tmp/s.aat.json"
ft_capture_store
ft_finalize
