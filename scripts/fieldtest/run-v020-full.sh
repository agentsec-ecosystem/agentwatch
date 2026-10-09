#!/usr/bin/env bash
# Full v0.2.0 field-test run: Layer-0 (v0.1.0 cases) then every v0.2.0 suite.
#
#   run-v020-full.sh                 # Layer-0 + all 15 suites
#   run-v020-full.sh s1-install ...  # Layer-0 + only these suites
#
# Builds the images ONCE, keeps one stack up across the whole run, resets state
# between cases in place (down -v only for `recycle` cases, which mutate durable /
# container state a soft reset cannot clear), and tears the stack down once at the
# end. Every result lands under field-test/v0.2.0/results/ (layer0 + s1..s15);
# field-test/v0.1.0/results/ is never written (lib.sh freeze guard).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FT_VERSION="${FT_VERSION:-v0.2.0}"
# STACK_KEEP=0 permanently; the stack is torn down once, at the end.
export STACK_KEEP=0
export FT_SHARED_STACK=1
# This runner owns the stack for the whole run: child runners must not tear it
# down between phases.
export FT_STACK_OWNED_BY_PARENT=1
# shellcheck source=lib.sh
source "$HERE/lib.sh"
export STACK_ON_NO_DOCKER=fail

ft_build_images || true

rc=0

echo "--- Layer-0 (v0.1.0 cases) -> results/layer0 ---"
layer0_ids="$(python3 - "$HERE/cases/registry.json" <<'PY'
import json, sys
reg = json.load(open(sys.argv[1]))
print(" ".join(c["id"] for c in reg if not str(c.get("kind", "")).startswith("v020")))
PY
)"
# shellcheck disable=SC2086
if ! FT_RUN_ID=layer0 bash "$HERE/run-all.sh" $layer0_ids; then
  rc=1
fi

echo "--- v0.2.0 suites -> results/s1..s15 ---"
if ! bash "$HERE/run-v020-all.sh" "$@"; then
  rc=1
fi

stack_teardown
echo "==> full v0.2.0 run complete (rc=$rc). Results under field-test/$FT_VERSION/results/"
exit "$rc"
