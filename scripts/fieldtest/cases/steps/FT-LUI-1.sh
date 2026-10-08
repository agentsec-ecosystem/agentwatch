ft_assert "ui-console-check" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -m agentwatch ui --check --host 127.0.0.1 --no-open
ft_assert "ui-module" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -c "import agentwatch.ui"
ft_assert "console-playwright" python3 "$REPO_ROOT/scripts/fieldtest/console_playwright.py"
ft_finalize
