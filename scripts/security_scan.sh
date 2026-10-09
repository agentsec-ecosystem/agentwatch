#!/usr/bin/env bash
# Reproducible first-party security scan (M24 24.3 Security audit / 24.5 OpenSSF).
#
# Runs four independent checks over agentwatch's own source and records machine-
# readable evidence:
#   1. gitleaks   — secrets across the full git history (config: .gitleaks.toml)
#   2. trufflehog — secrets in the working tree (first-party paths only)
#   3. pip-audit  — known vulnerabilities in each package's dependencies
#   4. egress     — no egress-capable runtime imports (scripts/dependency_egress_audit.py)
#
# Evidence is written to docs/release/v0.1.0/security-scan/ by default (override
# with SECURITY_SCAN_OUT=<dir>). The scan fails (exit 1) only on a real secret
# leak in first-party source or a dependency vulnerability, not on the
# documented, intentional redaction fixtures.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${SECURITY_SCAN_OUT:-docs/release/v0.2.0/security-scan}"
EXCLUDE="$ROOT/scripts/security/trufflehog-exclude.txt"
PACKAGES=(packages/python-sdk services/api services/analytics)
FIRST_PARTY_DIRS=(packages services apps scripts docs .github)

mkdir -p "$OUT"

# trufflehog v2 (a pip package) shadows the v3 binary on some machines — both
# accept `filesystem --help` (v2 just prints usage and exits 0), so detect v3 by
# a flag only it has and prefer the Homebrew v3 binary when present.
is_trufflehog_v3() {
  [ -n "$1" ] || return 1
  "$1" filesystem --help 2>&1 | grep -q -- "--exclude-paths"
}

resolve_trufflehog() {
  if [ -n "${TRUFFLEHOG:-}" ]; then echo "$TRUFFLEHOG"; return; fi
  local brew_bin
  brew_bin="$(brew --prefix trufflehog 2>/dev/null)/bin/trufflehog"
  if [ -x "$brew_bin" ] && is_trufflehog_v3 "$brew_bin"; then echo "$brew_bin"; return; fi
  if command -v trufflehog >/dev/null 2>&1 && is_trufflehog_v3 trufflehog; then
    echo "trufflehog"
    return
  fi
  echo "trufflehog"
}

TRUFFLEHOG="$(resolve_trufflehog)"
rc=0

require() {
  if ! command -v "$1" >/dev/null 2>&1 && [ ! -x "$1" ]; then
    echo "security-scan: missing required tool: $1" >&2
    rc=1
    return 1
  fi
}

echo "==> gitleaks (git history, $(git rev-list --count HEAD) commits)"
if require gitleaks; then
  gitleaks detect --config .gitleaks.toml \
    --report-format json --report-path "$OUT/gitleaks.json" --redact -v \
    || rc=1
fi

echo "==> trufflehog (working tree, first-party paths)"
if is_trufflehog_v3 "$TRUFFLEHOG"; then
  # trufflehog emits findings concurrently in nondeterministic order; sort so the
  # committed evidence is stable across runs. Scanner logs go to a temp file.
  err="$(mktemp)"
  "$TRUFFLEHOG" filesystem "${FIRST_PARTY_DIRS[@]}" \
    --no-update --no-verification --json -x "$EXCLUDE" \
    >"$OUT/trufflehog.jsonl" 2>"$err" || rc=1
  rm -f "$err"
  sort -o "$OUT/trufflehog.jsonl" "$OUT/trufflehog.jsonl"
  echo "    findings (unverified): $(wc -l <"$OUT/trufflehog.jsonl" | tr -d ' ')"
else
  echo "security-scan: missing required tool: trufflehog (v3)" >&2
  rc=1
fi

echo "==> pip-audit (dependency vulnerabilities)"
if require pip-audit; then
  for pkg in "${PACKAGES[@]}"; do
    slug="${pkg//\//_}"
    pip-audit "$pkg" --format json -o "$OUT/pip-audit-${slug}.json" || rc=1
  done
fi

echo "==> egress audit (no egress-capable runtime imports)"
python3 scripts/dependency_egress_audit.py || rc=1

if [ "$rc" -eq 0 ]; then
  echo "security-scan: clean (see $OUT)"
else
  echo "security-scan: FAILED (see $OUT)" >&2
fi
exit "$rc"
