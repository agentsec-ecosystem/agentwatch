#!/usr/bin/env bash
# Docker-stack smoke test (M14 Q5): build, boot, and verify the full stack.
#
# Confirms every service is running, postgres is ready, and every published
# endpoint responds (API health, web, Jaeger UI, OTel collector). Tears the stack
# and volumes down on exit so a run never leaves containers behind
# (STACK_KEEP=1 to keep them for debugging).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/stack_lib.sh
source "$ROOT/scripts/stack_lib.sh"

stack_require_docker
trap stack_teardown_on_exit EXIT

stack_up
stack_verify

echo "stack smoke OK: all services running and all endpoints responding"
