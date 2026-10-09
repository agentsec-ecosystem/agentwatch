#!/usr/bin/env bash
# Field-test helpers — thin layer over the existing scripts/stack_lib.sh.
#
# Reuses the repo's stack lifecycle primitive (stack_up / stack_verify /
# stack_teardown_on_exit) and adds per-case result capture. Results are written
# to field-test/v0.1.0/results/<UTC-ts>/ (see docs/field-test/v0.1.0/field-test-plan.md).
#
# Source from a runner:
#   source "$(dirname "$0")/lib.sh"
#   ft_require_docker || { ... fail ... }
#   trap ft_teardown_on_exit EXIT
#   ft_case_begin "$ID"
#   ... steps + ft_assert ...
#   ft_finalize
#   ft_case_end "$ID" "$FT_CASE_STATUS"
set -euo pipefail

FT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"      # scripts/fieldtest
REPO_ROOT="$(cd "$FT_DIR/../.." && pwd)"                    # repo root
# Load the field-test env file if present (OMLX endpoint/model, STACK_*, FT_TAG).
if [[ -f "$FT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$FT_DIR/.env"
  set +a
fi
# Results are version-scoped: field-test/<FT_VERSION>/results/<run-id>/.
# The v0.2.0 runner sets FT_VERSION=v0.2.0 (see run-suite.sh / `make fieldtest-v020`).
# FT_RESULTS_ROOT overrides the whole path when set.
FT_VERSION="${FT_VERSION:-v0.1.0}"
# FREEZE GUARD: the v0.1.0 field-test results are frozen forever and must never
# be written by a v0.2.0 run. This blocks any accidental target.
if [[ "${FT_VERSION}" == "v0.1.0" && "${FT_ALLOW_V010_WRITE:-0}" != "1" ]]; then
  echo "FATAL: refusing to write to field-test/v0.1.0 (frozen). Set FT_VERSION=v0.2.0." >&2
  echo "       (override only with FT_ALLOW_V010_WRITE=1, and only for the v0.1.0 report itself)" >&2
  exit 3
fi
RESULTS_ROOT="${FT_RESULTS_ROOT:-$REPO_ROOT/field-test/$FT_VERSION/results}"
# Stable run directory name (no timestamps). Override with FT_RUN_ID=... per step.
FT_RUN_ID="${FT_RUN_ID:-all}"
FT_RUN_DIR="$RESULTS_ROOT/$FT_RUN_ID"

# shellcheck source=../stack_lib.sh
source "$REPO_ROOT/scripts/stack_lib.sh"

# Use the base analyst stack plus the field-test recorder overlay.
STACK_COMPOSE=(docker compose \
  -f "$REPO_ROOT/docker-compose.yml" \
  -f "$FT_DIR/docker-compose.fieldtest.yml")
STACK_SERVICES=(recorder)
STACK_ENDPOINTS=()

FT_CASE_DIR=""
FT_CASE_STATUS="fail"
FT_ASSERT_FAILED=0
# Declare class (v0.2.0): FT_CASE_CLASS is "P/F" or "P/F|D" (from the registry);
# FT_CASE_DECLARED / FT_DECLARE_LIMITATION / FT_DECLARE_GATE are set by ft_declare.
FT_CASE_CLASS="${FT_CASE_CLASS:-P/F}"
FT_CASE_DECLARED=0
FT_DECLARE_LIMITATION=""
FT_DECLARE_GATE=""

# --- docker gate -------------------------------------------------------------
# Overrides stack_lib's stack_require_docker, which exits 0 on a missing daemon
# (a false green for a field test). This returns non-zero so the runner records
# a hard failure: a case that cannot run is a failed case, never a skip.
ft_require_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "FAIL: Docker is unavailable; field test cannot run." >&2
    return 3
  fi
}

# --- run directory -----------------------------------------------------------
ft_run_init() {
  mkdir -p "$FT_RUN_DIR"
  if [[ ! -f "$FT_RUN_DIR/env.json" ]]; then
    {
      printf '{"run_id":"%s","version":"%s","docker":"%s","compose":"%s","os":"%s","arch":"%s","omlx_base_url":"%s","omlx_model":"%s"}\n' \
        "$FT_RUN_ID" \
        "$FT_VERSION" \
        "$(docker --version 2>/dev/null || echo unknown)" \
        "$(docker compose version --short 2>/dev/null || echo unknown)" \
        "$(uname -s 2>/dev/null || echo unknown)" \
        "$(uname -m 2>/dev/null || echo unknown)" \
        "${OMLX_BASE_URL:-http://host.docker.internal:8000/v1}" \
        "${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}"
    } > "$FT_RUN_DIR/env.json"
  fi
}

# --- case lifecycle ----------------------------------------------------------
ft_case_begin() {
  local id="$1"
  ft_run_init
  FT_CASE_DIR="$FT_RUN_DIR/cases/$id"
  mkdir -p "$FT_CASE_DIR/artifacts"
  : > "$FT_CASE_DIR/commands.log"
  : > "$FT_CASE_DIR/stdout.log"
  : > "$FT_CASE_DIR/stderr.log"
  : > "$FT_CASE_DIR/assertions.ndjson"
  FT_CASE_STATUS="fail"
  FT_ASSERT_FAILED=0
  FT_CASE_DECLARED=0
  FT_DECLARE_LIMITATION=""
  FT_DECLARE_GATE=""
  echo "== case $id =="
}

# Resolve to `declared` for a P/F|D case whose environment is genuinely
# unavailable. Requires a named limitation + the release-gate item that permits
# "or declared" (PRD 40 §5-expanded 9/13; PRD 50; PRD 57 SBX-1/CNC-1). A
# `declared` outcome for a hard gate is invalid and fails the case.
ft_declare() {
  local limitation="$1" gate="${2:-}"
  if [[ "$FT_CASE_CLASS" != "P/F|D" ]]; then
    echo "  DECLARE-INVALID $limitation (case class is $FT_CASE_CLASS, not P/F|D)" >&2
    FT_ASSERT_FAILED=1
    return 1
  fi
  FT_CASE_DECLARED=1
  FT_DECLARE_LIMITATION="$limitation"
  FT_DECLARE_GATE="$gate"
  printf '{"name":"declared","ok":true,"limitation":"%s","release_gate_item":"%s"}\n' \
    "$limitation" "$gate" >> "$FT_CASE_DIR/assertions.ndjson"
  echo "  DECLARED $limitation"
}

ft_record() { printf '+ %s\n' "$*" >> "$FT_CASE_DIR/commands.log"; }

# Run a command, tee stdout/stderr, and return its exit code.
ft_run() {
  ft_record "$@"
  local rc=0
  "$@" >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log" || rc=$?
  return "$rc"
}

# Execute a shell command inside a service container.
ft_exec() {
  local service="$1"; shift
  ft_record "compose exec $service $*"
  local rc=0
  "${STACK_COMPOSE[@]}" exec -T "$service" "$@" \
    >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log" || rc=$?
  return "$rc"
}

ft_assert() {
  local name="$1"; shift
  if "$@" >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"; then
    printf '{"name":"%s","ok":true}\n' "$name" >> "$FT_CASE_DIR/assertions.ndjson"
    echo "  PASS $name"
    return 0
  fi
  FT_ASSERT_FAILED=1
  printf '{"name":"%s","ok":false}\n' "$name" >> "$FT_CASE_DIR/assertions.ndjson"
  echo "  FAIL $name" >&2
  return 1
}

# Record a failed assertion without running a command (for infrastructure
# failures: container up, daemon socket, empty store, 0 frames delivered).
ft_fail() {
  local name="$1"
  FT_ASSERT_FAILED=1
  printf '{"name":"%s","ok":false}\n' "$name" >> "$FT_CASE_DIR/assertions.ndjson"
  echo "  FAIL $name" >&2
}

# Record a passed assertion without running a command.
ft_pass() {
  local name="$1"
  printf '{"name":"%s","ok":true}\n' "$name" >> "$FT_CASE_DIR/assertions.ndjson"
  echo "  PASS $name"
}

ft_capture() {
  local src="$1" dest="$2"
  mkdir -p "$FT_CASE_DIR/artifacts/$dest"
  cp -R "$src"/. "$FT_CASE_DIR/artifacts/$dest/" 2>/dev/null || true
}

# Assert a shell command *inside the recorder* (no skip: true -> pass, false -> fail).
ft_assert_recorder() {
  local name="$1"; shift
  ft_assert "$name" ft_recorder bash -lc "$*"
}

ft_case_end() {
  local id="$1" status="${2:-$FT_CASE_STATUS}"
  FT_CASE_STATUS="$status"
  {
    printf '{\n'
    printf '  "id": "%s",\n' "$id"
    printf '  "status": "%s",\n' "$status"
    printf '  "class": "%s",\n' "$FT_CASE_CLASS"
    printf '  "declared": %s,\n' "$([[ "$FT_CASE_DECLARED" -eq 1 ]] && echo true || echo false)"
    if [[ "$FT_CASE_DECLARED" -eq 1 ]]; then
      printf '  "limitation": "%s",\n' "$FT_DECLARE_LIMITATION"
      printf '  "release_gate_item": "%s",\n' "$FT_DECLARE_GATE"
    fi
    printf '  "run_id": "%s",\n' "$FT_RUN_ID"
    printf '  "assertions": ['
    if [[ -s "$FT_CASE_DIR/assertions.ndjson" ]]; then
      paste -sd, "$FT_CASE_DIR/assertions.ndjson"
    fi
    printf ']\n}\n'
  } > "$FT_CASE_DIR/verdict.json"
  echo "== case $id: $status =="
}

ft_finalize() {
  # No skip: pass only if every assertion held. Any failure => fail.
  # A declared P/F|D case (environment genuinely unavailable) is `declared`,
  # which is a distinct terminal state, not a pass.
  if [[ "$FT_ASSERT_FAILED" -ne 0 ]]; then
    FT_CASE_STATUS="fail"
  elif [[ "$FT_CASE_DECLARED" -eq 1 ]]; then
    FT_CASE_STATUS="declared"
  else
    FT_CASE_STATUS="pass"
  fi
}

# Case-exit trap. In a shared-stack run the stack stays up across cases and is
# reset in place between them (see ft_reset_state and run-case.sh); the top-level
# runner tears it down once, at the end. A standalone case honors STACK_KEEP.
ft_teardown_on_exit() {
  local code=$?
  if [[ "${FT_SHARED_STACK:-0}" == "1" ]]; then
    exit "$code"
  fi
  if [[ "${STACK_KEEP:-}" == "1" ]]; then
    echo "==> STACK_KEEP=1 set; leaving the stack running"
    exit "$code"
  fi
  stack_teardown
  exit "$code"
}

# --- recorder lifecycle ------------------------------------------------------
FT_RECORDER_STORE=/data/agentwatch
FT_RECORDER_SOCKET=/run/agentwatch/agentwatch.sock

# Every case boots the FULL stack (all services) and verifies it is up. The stack
# is built once per run and kept up across cases; a non-recycle case is reset in
# place (ft_reset_state) instead of being destroyed. A `recycle` case mutates
# durable/container state that a soft reset cannot clear and is given a genuinely
# fresh stack (run-case.sh tears it down before it runs).
ft_up_recorder() {
  if _ft_stack_up; then
    ft_reset_state
    ft_pass "stack-reused"
  else
    _ft_boot_recorder_fresh
  fi
}

# --- build once + stack liveness ---------------------------------------------
# Build the images ONCE per run. Top-level runners call ft_build_images and export
# FT_IMAGES_BUILT=1, so every case's `up -d` skips `--build` (images do not change
# during a run). Without it (e.g. a standalone case) the first `up` builds.
ft_build_images() {
  if [[ "${FT_IMAGES_BUILT:-0}" == "1" ]]; then
    return 0
  fi
  mkdir -p "$FT_RUN_DIR"
  ft_record "compose build (once per run)"
  local rc=0
  if [[ "${FT_VERSION:-v0.1.0}" == "v0.2.0" ]]; then
    "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" build "${V020_SERVICES[@]}" \
      >> "$FT_RUN_DIR/.build.log" 2>&1 || rc=$?
  else
    "${STACK_COMPOSE[@]}" build >> "$FT_RUN_DIR/.build.log" 2>&1 || rc=$?
  fi
  export FT_IMAGES_BUILT=1
  return "$rc"
}

# Expected running services for the active version.
_ft_expected_services() {
  if [[ "${FT_VERSION:-v0.1.0}" == "v0.2.0" ]]; then
    printf '%s\n' "${V020_SERVICES[@]}"
  else
    printf '%s\n' postgres jaeger otel-collector api analytics web recorder verifier
  fi
}

# True when every expected service has a running container.
_ft_stack_up() {
  local svc cid
  while IFS= read -r svc; do
    cid="$("${STACK_COMPOSE[@]}" ps -q "$svc" 2>/dev/null)"
    [[ -n "$cid" ]] || return 1
    [[ "$(docker inspect --format '{{.State.Running}}' "$cid" 2>/dev/null)" == "true" ]] || return 1
  done < <(_ft_expected_services)
  return 0
}

# Bring up the full stack and verify it (used only when the stack is not already
# running). Build happens once per run, so this is `up -d` on the shared path.
_ft_boot_recorder_fresh() {
  if [[ "${FT_VERSION:-v0.1.0}" == "v0.2.0" ]]; then
    ft_up_v020
    ft_verify_v020
  else
    ft_up_all
    ft_verify_all
  fi
}

# --- per-case state reset (replaces `down -v`) -------------------------------
# Wipe the recorder store + socket and clear the analytics read-model tables so
# each case starts clean WITHOUT destroying containers or volumes. Only the
# recorder process is restarted; the rest of the stack stays up. Cases that need
# a genuinely fresh stack carry `recycle` and get a real `down -v` instead.
ft_reset_state() {
  ft_record "reset: restart recorder; wipe store+socket; truncate read-model"
  if "${STACK_COMPOSE[@]}" restart recorder \
      >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"; then
    ft_pass "reset-recorder-restart"
  else
    ft_fail "reset-recorder-restart"
    return 1
  fi
  ft_recorder bash -lc 'shopt -s dotglob; rm -rf /data/agentwatch/* /run/agentwatch/* 2>/dev/null; mkdir -p /data/agentwatch /run/agentwatch; true' \
    >/dev/null 2>>"$FT_CASE_DIR/stderr.log" || true
  local pgid
  pgid="$("${STACK_COMPOSE[@]}" ps -q postgres 2>/dev/null)"
  if [[ -n "$pgid" ]]; then
    docker exec "$pgid" psql -U analytics -d analytics -c \
      "DO \$\$ DECLARE r record; BEGIN FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') LOOP EXECUTE 'TRUNCATE TABLE '||quote_ident(r.tablename)||' RESTART IDENTITY CASCADE'; END LOOP; END \$\$;" \
      >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log" || true
  fi
  ft_pass "state-reset"
}

# --- v0.2.0 environment (M31 31.1) ------------------------------------------
# The base analyst stack + recorder/verifier + the v0.2.0 profile services
# (otel-grpc, fleet-h1..3, a2a-proxy, litellm, runner) and the managed-policy
# fixture. Defined in docker-compose.fieldtest.yml behind the v020/managed
# profiles; stack-v020.sh brings the same set up for manual runs.
V020_PROFILE_SERVICES=(otel-grpc fleet-h1 fleet-h2 fleet-h3 a2a-proxy litellm runner tempo)
V020_SERVICES=(postgres jaeger otel-collector api analytics web recorder verifier
  "${V020_PROFILE_SERVICES[@]}" managed-hooks)
# The profile flags that make the v0.2.0 services present. Single source of truth
# for both the harness (ft_up_v020) and the standalone stack-v020.sh/seed-v020.sh.
V020_PROFILES=(--profile v020 --profile managed --profile tempo)

ft_up_v020() {
  local args=(-d)
  [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || args+=(--build)
  ft_record "compose --profile v020 --profile tempo up ${args[*]} (v0.2.0 services)"
  if "${STACK_COMPOSE[@]}" "${V020_PROFILES[@]}" up "${args[@]}" "${V020_SERVICES[@]}" \
      >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"; then
    ft_pass "stack-up-v020"
  else
    ft_fail "stack-up-v020"
  fi
}

# Verify every base service (via ft_verify_all) plus each v0.2.0 service.
ft_verify_v020() {
  ft_verify_all
  local svc cid
  for svc in "${V020_PROFILE_SERVICES[@]}" managed-hooks; do
    cid="$("${STACK_COMPOSE[@]}" ps -q "$svc" 2>/dev/null)"
    if [[ -z "$cid" ]]; then
      printf '%-16s %-10s %s\n' "$svc" "DOWN" "container missing"
      ft_fail "svc-$svc"
      continue
    fi
    printf '%-16s %-10s %s\n' "$svc" "$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null)" "container up"
    ft_pass "svc-$svc"
  done
}

# Boot the FULL stack (all 8 services) and verify every container is up + every
# endpoint responds. Called by EVERY case so the whole stack is up before any
# assertions run.
ft_up_all() {
  local args=(-d)
  [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || args+=(--build)
  ft_record "compose up ${args[*]} (all services)"
  if "${STACK_COMPOSE[@]}" up "${args[@]}" postgres jaeger otel-collector api analytics web recorder verifier \
      >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"; then
    ft_pass "stack-up"
  else
    ft_fail "stack-up"
  fi
}

# Verify every service is running and every endpoint responds; records one
# assertion per service and per endpoint. Returns non-zero if any fail.
ft_verify_all() {
  local rc=0
  printf '%-16s %-10s %s\n' "SERVICE" "STATUS" "CHECK"
  for svc in postgres jaeger otel-collector api analytics web recorder verifier; do
    local cid
    cid="$("${STACK_COMPOSE[@]}" ps -q "$svc" 2>/dev/null)"
    if [[ -z "$cid" ]]; then
      printf '%-16s %-10s %s\n' "$svc" "DOWN" "container missing"
      ft_fail "svc-$svc"; rc=1; continue
    fi
    printf '%-16s %-10s %s\n' "$svc" "$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null)" "container up"
    ft_pass "svc-$svc"
  done
  _check "postgres"    "docker exec $("${STACK_COMPOSE[@]}" ps -q postgres) pg_isready -U analytics"
  _check "api-health"  "curl -sf --max-time 5 http://localhost:8100/api/v1/health"
  _check "jaeger"      "curl -sf --max-time 5 http://localhost:16686/api/services"
  _check "collector"   "curl -sf -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:4318/v1/traces -X POST -H 'Content-Type: application/json' -d '{}'"
  _check "web"         "curl -sf -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:5173/"
  _check "recorder"    "docker exec $("${STACK_COMPOSE[@]}" ps -q recorder) agentwatch --version"
  _check "omlx"        "curl -sf --max-time 5 http://localhost:8000/v1/models"
  return "$rc"
}

_check() {
  local name="$1"; shift
  if bash -lc "$*" >/dev/null 2>&1; then
    printf '%-16s %-10s %s\n' "$name" "OK" "responds"
    ft_pass "ep-$name"
  else
    printf '%-16s %-10s %s\n' "$name" "FAIL" "no response"
    ft_fail "ep-$name"
    return 1
  fi
}

# Run argv inside the recorder container.
ft_recorder() { ft_exec recorder "$@"; }

# Start the daemon in the background inside the recorder and wait for the socket.
# Replicates the production launcher (install.start_daemon) by recording the
# daemon pid, which crash-gap detection (F1) and stop-by-pid rely on.
ft_start_daemon() {
  if ! ft_recorder bash -lc \
      'mkdir -p /run/agentwatch; (agentwatch-daemon >/tmp/daemon.log 2>&1 &) ; \
       for i in $(seq 1 50); do [ -S "$AGENTWATCH_SOCKET" ] && exit 0; sleep 0.2; done; \
       echo "daemon socket did not appear" >&2; tail -20 /tmp/daemon.log >&2; exit 1'; then
    ft_fail "daemon-up"
    return
  fi
  ft_recorder bash -lc 'mkdir -p /data/agentwatch; pgrep -f "[a]gentwatch-daemon" | head -1 > /data/agentwatch/daemon.pid' || true
}

ft_stop_daemon() {
  ft_recorder bash -lc 'pkill -f agentwatch-daemon || true; sleep 0.3 || true'
}

# Emit hook frames through the real hook/socket path. Args passed to emit-hook.py.
# A delivery failure (frame neither delivered nor spooled) is a hard assertion.
ft_emit() {
  if ft_recorder python3 /ft/scripts/emit-hook.py "$@"; then
    ft_pass "emit"
  else
    ft_fail "emit"
  fi
}

# Copy the recorder store + daemon/container logs into the case artifacts and
# assert that the store actually holds records (an empty store is a failure,
# never a silent pass).
ft_capture_store() {
  ft_capture_store_soft
  if [[ -s "$FT_CASE_DIR/artifacts/store/records.jsonl" ]] && grep -q '"seq":' "$FT_CASE_DIR/artifacts/store/records.jsonl" 2>/dev/null; then
    ft_pass "store-has-records"
  else
    ft_fail "store-has-records"
  fi
}

# Copy the recorder store + logs WITHOUT asserting records — for cases that do
# not run the recorder daemon (OTLP probes, fidelity matrix on side stores).
ft_capture_store_soft() {
  local dest="$FT_CASE_DIR/artifacts/store"
  mkdir -p "$dest"
  local cid
  cid="$("${STACK_COMPOSE[@]}" ps -q recorder 2>/dev/null)"
  if [[ -n "$cid" ]]; then
    docker cp "$cid":"$FT_RECORDER_STORE"/. "$dest/" 2>/dev/null || true
    docker cp "$cid":/tmp/daemon.log "$dest/daemon.log" 2>/dev/null || true
    docker logs "$cid" > "$dest/container.log" 2>&1 || true
  fi
}

# Capture container logs for a service into artifacts/logs/<service>.log.
ft_capture_logs() {
  local service="$1"
  mkdir -p "$FT_CASE_DIR/artifacts/logs"
  "${STACK_COMPOSE[@]}" logs --no-color "$service" \
    > "$FT_CASE_DIR/artifacts/logs/$service.log" 2>&1 || true
}

# Retry a command until it succeeds or the timeout expires.
#   ft_wait_until NAME TIMEOUT cmd...
ft_wait_until() {
  local name="$1" timeout="$2"; shift 2
  local deadline=$((SECONDS + timeout))
  while ! "$@" >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"; do
    if (( SECONDS >= deadline )); then
      echo "  TIMEOUT waiting for $name" >&2
      return 1
    fi
    sleep 1
  done
  return 0
}
