ft_up_recorder
ft_start_daemon
ft_recorder python3 -c "import os,socket; s=socket.socket(socket.AF_UNIX); s.connect(os.environ['AGENTWATCH_SOCKET']); s.sendall(b'{not-json\n'); s.close()"
sleep 1
ft_assert_recorder "quarantined" "test -s /data/agentwatch/quarantine.jsonl"
ft_assert_recorder "chain-green" "agentwatch verify-store"
ft_capture_store
ft_finalize
