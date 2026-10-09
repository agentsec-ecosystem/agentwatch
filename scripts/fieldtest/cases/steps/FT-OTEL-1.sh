ft_up_recorder
ft_start_daemon
ft_emit --corpus secrets
ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch --tree 3"
ft_assert "span-tree-2-backends" python3 "$REPO_ROOT/scripts/fieldtest/otel_tree_check.py"
ft_capture_store
ft_finalize
