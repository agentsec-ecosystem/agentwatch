#!/usr/bin/env bash
# Bring the v0.2.0 field-test environment up/down/verify for manual use.
# The same service set that run-suite.sh boots per case.
#
#   stack-v020.sh up       # build + start every v0.2.0 service
#   stack-v020.sh down     # tear down (and drop volumes)
#   stack-v020.sh ps       # show status
#   stack-v020.sh verify   # list running services (exit 1 if any is missing)
#
# Results are written by the runners to field-test/v0.2.0/results/; this script
# only manages the containers.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

COMPOSE=(docker compose \
  -f "$REPO_ROOT/docker-compose.yml" \
  -f "$HERE/docker-compose.fieldtest.yml" \
  --profile v020 --profile managed --profile tempo)

SERVICES=(postgres jaeger otel-collector api analytics web recorder verifier
  otel-grpc fleet-h1 fleet-h2 fleet-h3 a2a-proxy litellm runner managed-hooks)

case "${1:-}" in
  up)
    "${COMPOSE[@]}" up -d --build "${SERVICES[@]}"
    ;;
  down)
    "${COMPOSE[@]}" down -v
    ;;
  ps)
    "${COMPOSE[@]}" ps
    ;;
  verify)
    running="$("${COMPOSE[@]}" ps --services --filter status=running | sort)"
    rc=0
    for svc in "${SERVICES[@]}"; do
      if grep -qx "$svc" <<<"$running"; then
        printf '%-16s %s\n' "$svc" up
      else
        printf '%-16s %s\n' "$svc" DOWN
        rc=1
      fi
    done
    exit "$rc"
    ;;
  reset)
    "${COMPOSE[@]}" down -v
    "${COMPOSE[@]}" up -d --build "${SERVICES[@]}"
    ;;
  *)
    echo "usage: stack-v020.sh up|down|ps|verify|reset" >&2
    exit 2
    ;;
esac
