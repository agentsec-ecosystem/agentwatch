#!/usr/bin/env bash
# Bring the v0.2.0 field-test environment up/down/verify for manual use.
# The same service set that run-suite.sh boots per case.
#
#   stack-v020.sh up       # build + start every v0.2.0 service
#   stack-v020.sh down     # tear down (and drop volumes)
#   stack-v020.sh ps       # show status
#   stack-v020.sh verify   # list running services (exit 1 if any is missing)
#   stack-v020.sh reset    # down -v + up
#
# Single source of truth: this reuses lib.sh's STACK_COMPOSE, V020_PROFILES and
# V020_SERVICES (never re-declares the compose files or the service list).
# Results are written by the runners to field-test/v0.2.0/results/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

case "${1:-}" in
  up)
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" up -d --build "${V020_SERVICES[@]}"
    ;;
  down)
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" down -v
    ;;
  ps)
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" ps
    ;;
  verify)
    running="$("${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" ps --services --filter status=running | sort)"
    rc=0
    for svc in "${V020_SERVICES[@]}"; do
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
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" down -v
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" up -d --build "${V020_SERVICES[@]}"
    ;;
  *)
    echo "usage: stack-v020.sh up|down|ps|verify|reset" >&2
    exit 2
    ;;
esac
