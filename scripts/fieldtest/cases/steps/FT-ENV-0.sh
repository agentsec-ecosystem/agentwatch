ft_assert "first-run-timing" bash -lc "cd '$REPO_ROOT' && python3 scripts/first_run_timing.py"
ft_assert "naming-guard" bash -lc "cd '$REPO_ROOT' && python3 -c 'import agentwatch.naming'"
ft_finalize
