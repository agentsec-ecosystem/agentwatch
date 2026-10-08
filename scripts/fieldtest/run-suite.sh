#!/usr/bin/env bash
# Run one v0.2.0 field-test suite: every case whose registry `suite` matches.
# Usage:
#   run-suite.sh SUITE              # e.g. s1-install
#   run-suite.sh SUITE FT-AAT-1     # only these cases within the suite
#
# Results land under field-test/v0.2.0/results/<SUITE>/ (version-scoped), per
# docs/field-test/v0.2.0/field-test-plan.md §10. There is no skip: a case that
# cannot run is recorded as a failure. P/F|D cases may resolve to `declared`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE="${1:-}"
shift || true
if [[ -z "$SUITE" ]]; then
  {
    echo "usage: run-suite.sh SUITE [CASE...]"
    echo "suites: s1-install s2-interop s3-harness s4-detectors s5-identity"
    echo "        s6-surfaces s7-platform s8-apv s9-capability s10-provenance"
    echo "        s11-console s12-governance s13-investigation s14-outcomes s15-hostile"
  } >&2
  exit 2
fi

export FT_VERSION="${FT_VERSION:-v0.2.0}"
export FT_RUN_ID="$SUITE"
# STACK_KEEP=0 permanently: every run tears the stack down at the end.
export STACK_KEEP=0
# Shared stack across cases: built once, kept up, reset in place between cases.
export FT_SHARED_STACK=1
# shellcheck source=lib.sh
source "$HERE/lib.sh"
export STACK_ON_NO_DOCKER=fail
ft_build_images || true

ids=("$@")
if [[ ${#ids[@]} -eq 0 ]]; then
  while IFS= read -r id; do
    [[ -n "$id" ]] && ids+=("$id")
  done < <(python3 - "$HERE/cases/registry.json" "$SUITE" <<'PY'
import json, sys
try:
    registry = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    registry = []
for case in registry:
    if case.get("suite") == sys.argv[2]:
        print(case["id"])
PY
)
fi

if [[ ${#ids[@]} -eq 0 ]]; then
  echo "run-suite: no cases found for suite '$SUITE'" >&2
  exit 2
fi

echo "==> suite $SUITE: ${#ids[@]} case(s) -> $FT_RUN_DIR"

rc=0
for id in "${ids[@]}"; do
  echo
  echo "################ $id ################"
  # Shared stack: non-recycle cases are reset in place; `recycle` cases get a
  # fresh `down -v` + boot (handled in run-case.sh). The stack is torn down once,
  # at the end.
  if ! bash "$HERE/run-case.sh" "$id"; then
    rc=1
  fi
done

echo
echo "==> Aggregating results into $FT_RUN_DIR"
python3 "$HERE/collect-results.py" "$FT_RUN_DIR" --expect "${ids[@]}" || true

# One teardown per run — unless a parent runner owns the stack.
if [[ "${FT_STACK_OWNED_BY_PARENT:-0}" != "1" ]]; then
  stack_teardown
fi

exit "$rc"
