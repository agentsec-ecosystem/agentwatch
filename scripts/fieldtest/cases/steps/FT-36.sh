ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
mkdir -p "$REPO_ROOT/docs/assets/screenshots"
ft_assert "playwright-screenshots" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && npx playwright install chromium && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright test tests/e2e/screenshots.spec.ts"
for name in dashboard-overview dashboard-to-fleet fleet-default timeline-normal timeline-spans anomalies-default anomalies-critical compare-deltas; do
  ft_assert "guide-$name" test -f "$REPO_ROOT/docs/assets/screenshots/$name.png"
done
mkdir -p "$FT_CASE_DIR/artifacts/screenshots"
cp "$REPO_ROOT/docs/assets/screenshots/"*.png "$FT_CASE_DIR/artifacts/screenshots/" 2>/dev/null || true
ft_finalize
