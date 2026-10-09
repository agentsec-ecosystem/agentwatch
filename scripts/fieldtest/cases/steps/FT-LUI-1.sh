ft_assert "ui-console-check" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -m agentwatch ui --check --host 127.0.0.1 --no-open
ft_assert "ui-module" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -c "import agentwatch.ui"
ft_assert "console-playwright" python3 "$REPO_ROOT/scripts/fieldtest/console_playwright.py"

ft_assert "console-semantics" python3 "$REPO_ROOT/scripts/fieldtest/shipped_tests.py" packages/python-sdk/tests/test_console.py packages/python-sdk/tests/test_accessibility.py
ft_finalize
