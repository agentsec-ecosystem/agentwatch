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

trap ft_teardown_on_exit EXIT
ft_case_begin "$ID"

if [[ "$REQUIRES" == *docker* ]] && ! ft_require_docker; then
  # No Docker: the case fails (never a silent skip).
  printf '{"name":"docker-available","ok":false}\n' >> "$FT_CASE_DIR/assertions.ndjson"
  ft_case_end "$ID" "fail"
  exit 1
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
