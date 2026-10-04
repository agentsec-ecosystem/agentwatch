#!/usr/bin/env bash
# Shared compose-stack lifecycle helpers (M14 Q5).
#
# This is the reusable stack primitive for the Docker-backed field tests
# (M23 23.1, issue #141): they source this file to bring the compose stack up,
# assert every service is running, probe every published endpoint until it
# responds, and tear the stack (and its volumes) down on exit — so a test run
# never leaves containers "in the wild".
#
# Source this from a runner script:
#   source "$(dirname "$0")/stack_lib.sh"
#   stack_require_docker
#   trap stack_teardown_on_exit EXIT
#   stack_up
#   stack_verify          # services running + endpoints responding
#   ...                   # migrate / seed / drive the scenario
#   # teardown runs from the EXIT trap
#
# Extend by appending to STACK_SERVICES / STACK_ENDPOINTS before stack_verify.
#
# Env:
#   STACK_KEEP=1   leave the stack running on exit (debugging only)
#   STACK_TIMEOUT  seconds to wait per phase (default 180)

STACK_COMPOSE=(docker compose)
STACK_SERVICES=(postgres jaeger otel-collector api analytics web)
STACK_TIMEOUT="${STACK_TIMEOUT:-180}"

# Published endpoints: "name|url|expected_http_code_or_any".
STACK_ENDPOINTS=(
  "api|http://localhost:8100/api/v1/health|200"
  "web|http://localhost:5173/|200"
  "jaeger|http://localhost:16686/|200"
  "otel-collector|http://localhost:4318/|any"
)

stack_require_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "SKIPPED: Docker is unavailable; cannot run the compose-backed check." >&2
    echo "Start Docker (or use a runner that has it) to exercise this." >&2
    # CI may skip gracefully; a field test must never report a pass for a run
    # that did not happen, so fieldtest sets STACK_ON_NO_DOCKER=fail (M23).
    if [[ "${STACK_ON_NO_DOCKER:-skip}" == "fail" ]]; then
      exit 3
    fi
    exit 0
  fi
}

stack_up() {
  echo "==> Bringing up the stack"
  "${STACK_COMPOSE[@]}" up -d --build
}

stack_dump() {
  echo "--- docker compose ps ---" >&2
  "${STACK_COMPOSE[@]}" ps >&2 || true
  echo "--- docker compose logs (tail) ---" >&2
  "${STACK_COMPOSE[@]}" logs --no-color 2>&1 | tail -120 >&2 || true
}

stack_wait_services() {
  echo "==> Waiting for every service to be running"
  local deadline=$((SECONDS + STACK_TIMEOUT))
  while :; do
    local running missing="" service
    running="$("${STACK_COMPOSE[@]}" ps --services --filter status=running 2>/dev/null | sort)"
    for service in "${STACK_SERVICES[@]}"; do
      if ! grep -qx "$service" <<<"$running"; then
        missing="$missing $service"
      fi
    done
    if [[ -z "$missing" ]]; then
      echo "    all services running: ${STACK_SERVICES[*]}"
      return 0
    fi
    if (( SECONDS >= deadline )); then
      echo "!! services not running:$missing" >&2
      stack_dump
      return 1
    fi
    sleep 2
  done
}

_stack_wait_pg_ready() {
  local deadline=$((SECONDS + STACK_TIMEOUT))
  until "${STACK_COMPOSE[@]}" exec -T postgres pg_isready -U analytics >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "!! postgres did not become ready" >&2
      stack_dump
      return 1
    fi
    sleep 2
  done
}

stack_probe() {
  local name="$1" url="$2" expected="$3"
  local deadline=$((SECONDS + STACK_TIMEOUT)) code
  while :; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"
    if [[ "$expected" == "any" ]]; then
      # Any HTTP response (including 404) proves the socket is online.
      if [[ -n "$code" && "$code" != "000" ]]; then
        echo "    $name OK ($url -> HTTP $code)"
        return 0
      fi
    elif [[ "$code" == "$expected" ]]; then
      echo "    $name OK ($url -> HTTP $code)"
      return 0
    fi
    if (( SECONDS >= deadline )); then
      echo "!! $name not responding ($url; last HTTP '$code', expected '$expected')" >&2
      stack_dump
      return 1
    fi
    sleep 2
  done
}

stack_wait_endpoints() {
  echo "==> Waiting for endpoints to respond"
  _stack_wait_pg_ready
  echo "    postgres OK (pg_isready)"
  local entry name url expected
  for entry in "${STACK_ENDPOINTS[@]}"; do
    IFS='|' read -r name url expected <<<"$entry"
    stack_probe "$name" "$url" "$expected"
  done
}

# One-shot readiness gate: every service running, postgres ready, every published
# endpoint responding. This is the primitive the Docker field tests reuse.
stack_verify() {
  stack_wait_services
  stack_wait_endpoints
}

stack_teardown() {
  echo "==> Tearing down the stack (and volumes)"
  "${STACK_COMPOSE[@]}" down -v >/dev/null 2>&1 || true
}

stack_teardown_on_exit() {
  local code=$?
  if [[ "${STACK_KEEP:-}" == "1" ]]; then
    echo "==> STACK_KEEP=1 set; leaving the stack running"
    exit "$code"
  fi
  stack_teardown
  exit "$code"
}
