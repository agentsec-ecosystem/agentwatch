#!/usr/bin/env bash
# Run one field-test case. Usage:
#   run-case.sh CASE-ID [--keep]
#
# Sources cases/steps/<CASE-ID>.sh, which boots what it needs, runs assertions,
# and calls ft_finalize (which sets FT_CASE_STATUS pass only if every assertion
# held). There is no skip: a case that does not pass is a failed case.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ID="${1:-}"
KEEP="${2:-}"
if [[ -z "$ID" ]]; then
  echo "usage: run-case.sh CASE-ID [--keep]" >&2
  exit 2
fi

# shellcheck source=lib.sh
source "$HERE/lib.sh"
export STACK_ON_NO_DOCKER=fail
if [[ "$KEEP" == "--keep" ]]; then export STACK_KEEP=1; fi

STEP="$HERE/cases/steps/$ID.sh"
if [[ ! -f "$STEP" ]]; then
  echo "unknown case $ID (no steps at $STEP)" >&2
  exit 2
fi

# Docker is required only for cases that declare it (FT-27 runs host-native).
REQUIRES="$(python3 - "$HERE/cases/registry.json" "$ID" <<'PY'
import json, sys
try:
    registry = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    registry = []
match = next((c for c in registry if c.get("id") == sys.argv[2]), {})
print(match.get("requires", ""))
PY
)"

# Declare class (P/F | P/F|D) is carried from the registry so the verdict and the
# declare-class gate agree (v0.2.0 only; v0.1.0 cases default to P/F).
FT_CASE_CLASS="$(python3 - "$HERE/cases/registry.json" "$ID" <<'PY'
import json, sys
try:
    registry = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    registry = []
match = next((c for c in registry if c.get("id") == sys.argv[2]), {})
print(match.get("class", "P/F"))
PY
)"
export FT_CASE_CLASS

# Recycle flag: a `recycle` case mutates durable/container state that an in-place
# state reset cannot clear, so it gets a genuinely fresh stack (run-case tears it
# down before it runs; its own ft_up_recorder then boots clean).
FT_RECYCLE="$(python3 - "$HERE/cases/registry.json" "$ID" <<'PY'
import json, sys
try:
    registry = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    registry = []
match = next((c for c in registry if c.get("id") == sys.argv[2]), {})
print("1" if match.get("recycle") else "0")
PY
)"
export FT_RECYCLE

trap ft_teardown_on_exit EXIT
ft_case_begin "$ID"

if [[ "$REQUIRES" == *docker* ]] && ! ft_require_docker; then
  # No Docker: the case fails (never a silent skip).
  printf '{"name":"docker-available","ok":false}\n' >> "$FT_CASE_DIR/assertions.ndjson"
  ft_case_end "$ID" "fail"
  exit 1
fi

# Shared-stack run: recycle cases get a clean slate; every other case is reset in
# place by ft_reset_state (called from ft_up_recorder) and shares the stack.
if [[ "$FT_RECYCLE" == "1" ]]; then
  ft_record "recycle: down -v before case"
  stack_teardown
fi

# Run the step without errexit so that a single failed assertion does not abort
# before the verdict is written; ft_finalize decides pass/fail from the
# assertion flag, and a non-zero return is treated as a failure.
set +e
# shellcheck source=/dev/null
source "$STEP"
step_rc=$?
set -e

if [[ "$step_rc" -ne 0 ]]; then
  FT_ASSERT_FAILED=1
fi
ft_finalize
ft_case_end "$ID" "$FT_CASE_STATUS"

[[ "$FT_CASE_STATUS" == "pass" ]] || exit 1
