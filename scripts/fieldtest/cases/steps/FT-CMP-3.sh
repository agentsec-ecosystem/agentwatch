ft_up_recorder
ft_start_daemon
ft_assert_recorder "all-templates" "python3 /ft/scripts/compliance_templates.py"
ft_assert_recorder "key-rotation" "python3 /ft/scripts/checkpoint_rotate.py"
ft_capture_store_soft
ft_finalize
