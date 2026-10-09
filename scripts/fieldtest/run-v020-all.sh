#!/usr/bin/env bash
# Run every v0.2.0 field-test suite (S1-S15) and collect results.
# Results land under field-test/v0.2.0/results/<suite>/ (per plan §10).
#
#   run-v020-all.sh              # all 15 suites
#   run-v020-all.sh s1-install   # just these suites
#
# Build once, keep the stack up across all suites, reset state between cases
# (down -v only for `recycle` cases), and tear down once at the end. STACK_KEEP=0
# is permanent.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FT_VERSION="${FT_VERSION:-v0.2.0}"
export STACK_KEEP=0
export FT_SHARED_STACK=1
# Child suites share this runner's stack (they must not tear it down).
_OWN_STACK="${FT_STACK_OWNED_BY_PARENT:-0}"
export FT_STACK_OWNED_BY_PARENT=1
# shellcheck source=lib.sh
source "$HERE/lib.sh"
export STACK_ON_NO_DOCKER=fail
ft_build_images || true

ALL=(s1-install s2-interop s3-harness s4-detectors s5-identity s6-surfaces s7-platform
     s8-apv s9-capability s10-provenance s11-console s12-governance s13-investigation
     s14-outcomes s15-hostile)

suites=("$@")
if [[ ${#suites[@]} -eq 0 ]]; then
  suites=("${ALL[@]}")
fi

echo "==> v0.2.0 field-test run: ${#suites[@]} suite(s); STACK_KEEP=$STACK_KEEP; OMLX_MODEL=${OMLX_MODEL:-unset}"
rc=0
for s in "${suites[@]}"; do
  echo
  echo "############## suite $s ##############"
  if ! bash "$HERE/run-suite.sh" "$s"; then
    echo "!! suite $s had failures" >&2
    rc=1
  fi
done
echo
echo "==> run complete (rc=$rc). Results under field-test/$FT_VERSION/results/"

# One teardown per run — unless a parent runner owns the stack.
if [[ "${_OWN_STACK:-0}" != "1" ]]; then
  stack_teardown
fi

exit "$rc"
