#!/usr/bin/env bash
# Boot the compose stack and run the Playwright E2E suite (M8/M14 Q5).
#
# Shared by `make e2e` and .github/workflows/e2e.yml so CI runs the same path a
# developer does: bring the stack up, verify every service + endpoint, seed the
# read model, run Playwright, then tear the stack down (STACK_KEEP=1 to keep it).
#
# Requires: docker compose, python3 with asyncpg (make setup), Node with
# apps/web deps installed, and Playwright browsers installed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/stack_lib.sh
source "$ROOT/scripts/stack_lib.sh"

stack_require_docker
trap stack_teardown_on_exit EXIT

stack_up
stack_verify

echo "==> Creating the read-model tables"
python3 scripts/migrate-db.py

echo "==> Seeding e2e data"
python3 scripts/seed-e2e-data.py

echo "==> Ensuring Playwright chromium is installed"
# CI installs browsers in a prior step; a local run must too (M23 pre-work fix).
if [[ "${PLAYWRIGHT_SKIP_BROWSER_INSTALL:-0}" != "1" ]]; then
  npx playwright install chromium
fi

echo "==> Running Playwright"
cd apps/web
npx playwright test
