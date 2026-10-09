ft_up_recorder
ft_start_daemon
ft_assert_recorder "all-templates" "python3 /ft/scripts/compliance_templates.py"
ft_assert_recorder "key-rotation" "python3 /ft/scripts/checkpoint_rotate.py"
ft_assert "rotation-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_signing_posture.py
ft_capture_store_soft
ft_finalize
