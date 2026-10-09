ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "incident-export" "agentwatch evidence ft04 --include incident-report.json --out /tmp/inc.zip && test -s /tmp/inc.zip"
ft_assert_recorder "no-auto-submit" "! agentwatch evidence --help | grep -qi submit"
ft_capture_store_soft
ft_finalize
