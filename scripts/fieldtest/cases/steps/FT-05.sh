ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
# Corrupt a *record* line (line 1 is the format header; line 3 is seq 1).
ft_recorder bash -lc 'sed -i "3s/./X/" /data/agentwatch/records.jsonl'
ft_assert_recorder "tamper-detected" "! agentwatch verify-store"
ft_assert_recorder "break-at-seq1" "agentwatch verify-store 2>&1 | grep -q 'seq 1'"
ft_capture_store
ft_finalize
