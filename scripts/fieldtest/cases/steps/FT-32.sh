ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
ft_assert "playwright-a11y" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && npx playwright install chromium && npx playwright test tests/e2e/a11y.spec.ts"
ft_finalize
