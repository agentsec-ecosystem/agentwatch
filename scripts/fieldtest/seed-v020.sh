#!/usr/bin/env bash
# Seed the v0.2.0 field-test store (fixtures) inside a service container.
# Usage: seed-v020.sh [SERVICE]      (default: recorder)
#
# Single source of truth: reuses lib.sh's STACK_COMPOSE + V020_PROFILES and the
# existing seed-fixtures.py primitive (no re-declared compose/service list).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"
SVC="${1:-recorder}"

echo "==> Seeding $SVC store"
"${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" exec -T "$SVC" \
  python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl --out /tmp/ft-fixtures
echo "==> Seeded."
