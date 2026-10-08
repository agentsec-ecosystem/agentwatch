ft_up_recorder
ft_start_daemon
ft_assert_recorder "langgraph-instrument" "python3 /ft/scripts/drive-agent.py --session ft-lg --framework langgraph && agentwatch verify-store"
ft_capture_store_soft
ft_finalize
