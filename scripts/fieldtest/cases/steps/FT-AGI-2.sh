ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "skill-answers" "python3 /ft/scripts/investigation_skill.py"
ft_capture_store_soft
ft_finalize
