#!/usr/bin/env bash
# Local release dry-run (M24 24.4): build the SDK, generate the SBOM + checksums,
# and run `agentwatch verify-release` over the result.
#
# Signing (Sigstore/cosign) and SLSA provenance require a CI OIDC identity, so
# they are exercised by `.github/workflows/release.yml` on a `v*` tag, not here;
# this dry-run verifies everything that is verifiable without an identity token.
#
# Usage: scripts/release/dry_run.sh [DIST_DIR]
#   DIST_DIR defaults to a fresh temp directory (nothing is written into the repo).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import build" >/dev/null 2>&1; then
  echo "release-dry-run: the 'build' package is required (pip install build)" >&2
  exit 2
fi

DIST="${1:-$(mktemp -d)/dist}"
mkdir -p "$DIST"

echo "==> build sdist + wheel -> $DIST"
"$PYTHON" -m build --no-isolation packages/python-sdk --outdir "$DIST" >/dev/null

echo "==> generate SBOM (CycloneDX)"
"$PYTHON" scripts/release/generate_sbom.py --output "$DIST/sbom.cdx.json"

echo "==> checksums"
"$PYTHON" scripts/release/checksums.py --dist "$DIST"

echo "==> verify-release (unsigned)"
VERIFY_OUT="$(dirname "$DIST")/verify.json"
PYTHONPATH="$ROOT/packages/python-sdk/src" \
  "$PYTHON" -m agentwatch verify-release "$DIST" --allow-unsigned --json \
  | tee "$VERIFY_OUT"

echo "release-dry-run: OK ($DIST)"
