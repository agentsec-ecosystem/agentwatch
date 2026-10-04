ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "dir-0700" '[ "$(stat -c %a /data/agentwatch)" = 700 ]'
ft_assert_recorder "records-0600" '[ "$(stat -c %a /data/agentwatch/records.jsonl)" = 600 ]'
ft_capture_store
ft_finalize
