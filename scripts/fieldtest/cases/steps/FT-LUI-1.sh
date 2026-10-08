ft_assert "ui-console-check" bash -lc "agentwatch ui --check --host 127.0.0.1 --no-open"
ft_assert "ui-module" python3 -c "import agentwatch.ui"
ft_assert "console-playwright" python3 "$REPO_ROOT/scripts/fieldtest/console_playwright.py"
ft_finalize
