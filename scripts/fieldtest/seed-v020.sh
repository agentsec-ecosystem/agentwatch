#!/usr/bin/env bash
# Seed the v0.2.0 field-test store (fixtures) inside a service container.
# Usage: seed-v020.sh [SERVICE]      (default: recorder)
# The same service set stack-v020.sh brings up; results land in the container
# store at /data/agentwatch, captured per-case into field-test/v0.2.0/results/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SVC="${1:-recorder}"

COMPOSE=(docker compose \
  -f "$REPO_ROOT/docker-compose.yml" \
  -f "$HERE/docker-compose.fieldtest.yml" \
  --profile v020 --profile managed --profile tempo)

echo "==> Seeding $SVC store"
"${COMPOSE[@]}" exec -T "$SVC" \
  python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl --out /tmp/ft-fixtures
echo "==> Seeded."
