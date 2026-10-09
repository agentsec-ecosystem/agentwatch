ft_assert "first-run-timing" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 "$REPO_ROOT/scripts/first_run_timing.py"
ft_assert "naming-guard" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 "$REPO_ROOT/scripts/fieldtest/naming_guard.py"
ft_finalize
