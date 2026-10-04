#!/usr/bin/env bash
# Run the whole field-test suite (or a subset). Usage:
#   run-all.sh                 # all cases, in registry order
#   run-all.sh FT-04 FT-15     # only these
#
# Results are written once to field-test/v0.1.0/results/<UTC-ts>/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"
export STACK_ON_NO_DOCKER=fail

# No global Docker gate: each case declares whether it needs Docker (FT-27 runs
# host-native). A case that cannot run is recorded as a failure, never skipped.
export FT_RUN_ID="${FT_RUN_ID:-all}"
ft_run_init

ids=("$@")
if [[ ${#ids[@]} -eq 0 ]]; then
  while IFS= read -r step; do
    ids+=("$(basename "$step" .sh)")
  done < <(ls "$HERE"/cases/steps/*.sh 2>/dev/null | sort)
fi

rc=0
for id in "${ids[@]}"; do
  echo
  echo "################ $id ################"
  if ! bash "$HERE/run-case.sh" "$id"; then
    rc=1
  fi
done

echo
echo "==> Aggregating results into $FT_RUN_DIR"
python3 "$HERE/collect-results.py" "$FT_RUN_DIR" --expect "${ids[@]}" || true

exit "$rc"
