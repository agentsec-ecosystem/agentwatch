ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "agent-trace-export" "python3 /ft/scripts/provenance-repo.py --agent-trace"
ft_capture_store_soft
ft_finalize
