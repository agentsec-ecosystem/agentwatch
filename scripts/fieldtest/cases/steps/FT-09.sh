ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
# Run the full Playwright suite; the screenshots spec writes the user-guide PNGs
# straight into docs/assets/screenshots so the guide images stay fresh.
mkdir -p "$REPO_ROOT/docs/assets/screenshots" "$FT_CASE_DIR/artifacts/screenshots"
ft_assert "playwright" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright install chromium && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright test"
for name in dashboard-overview dashboard-to-fleet fleet-default timeline-normal timeline-spans anomalies-default anomalies-critical compare-deltas; do
  ft_assert "guide-$name" test -f "$REPO_ROOT/docs/assets/screenshots/$name.png"
done
cp "$REPO_ROOT/docs/assets/screenshots/"*.png "$FT_CASE_DIR/artifacts/screenshots/" 2>/dev/null || true
ft_finalize
