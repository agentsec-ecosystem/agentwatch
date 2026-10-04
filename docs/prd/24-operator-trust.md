# PRD 24 — Operator Trust & Consent

**BLUF:** Make guarantees visible and installs consensual: `verify-privacy`, consent-first `init`, and harness preflight.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### G1. `agentwatch verify-privacy` — prove the redaction story · M5 · #188

**Why (evidence).** "No secrets at rest" is a claim. The attack pack runs in CI, but the operator
cannot run it against **their own configuration and store** or hand the output to compliance. For
a security product, an unprovable guarantee is a marketing line.

**Behavior.** One command: (1) runs the secret corpus through the *current* config; (2) scans the
*current* store (and quarantine/spool — resolve the B4 raw-quarantine tension here) for any marker
leakage; (3) prints a verdict — privacy mode, checks passed/failed, leaks with locations — in a
shareable form.

**Data & schema impact.** New `agentwatch/verify_privacy.py` composing `selftest` + `secrets` +
a store scan. No schema change.

**Security & privacy.** Read-only; the output must not itself print a leaked secret (print
locations/kinds, redact the value).

**Edge cases.** Empty store → pass with note. Quarantine containing raw secrets (B4) → decide
whether that is a "leak" for the report (recommended: report quarantine as a distinct,
documented category, not a failure, because it is owner-only and never exported — D-19.20).
Unreadable store → fail with the reason.

**Dependencies.** selftest/secrets (M4); store (M4); B4.

**Testing.** Clean store passes; planted leak named by location without echoing it; quarantine
category reported distinctly.

**Risks & mitigations.** A passing report creating false confidence about quarantine (documented
category + B4 decision).

**Decision.** D-19.20 (quarantine in the privacy verdict).

### G3. Consent-first `init` (+ `--dry-run`) · M5 · #190

**Why (evidence).** Installing hooks into someone's Claude Code config is invasive; silent writes
earn distrust. Users should never be surprised by what changed on their machine (the git-config
lesson).

**Behavior.** `init` prints exactly what it will write, where, and what will be captured, before
writing; `--yes` for scripts; `--dry-run` shows the precise diff; `uninstall` provably restores
the prior file byte-for-byte.

**Data & schema impact.** `install.py` gains a plan/diff step; uninstall already preserves
unrelated settings — prove it.

**Security & privacy.** Transparency is the point; the summary states what content is captured
under the current mode.

**Edge cases.** Pre-existing file with unrelated hooks → diff shows only our additions.
Interactive vs non-interactive (default to dry-run unless `--yes`? recommended: prompt when a TTY,
require `--yes` otherwise).

**Dependencies.** `install.py` (M3).

**Testing.** Dry-run produces a diff and writes nothing; uninstall restores byte-identical prior
file; non-TTY without `--yes` does not write.

**Risks & mitigations.** Prompt fatigue (clear, short summary).

**Decision.** D-19.22 (TTY prompt vs require --yes).

### G4. `init` preflight (harness version + trust gating) · M5 · #191

**Why (evidence).** The top support cost will be environment mismatch: an old `claude` version,
project hooks gated by workspace trust in headless `-p` runs, stale PATH entries. We hit
harness-doc drift ourselves in M3; users will hit harness-version drift.

**Behavior.** Before installing, `init` checks the Claude Code version against a tested range
(from the compatibility matrix, N4), verifies the hook schema we generate matches, and warns when
headless `-p` runs will not fire project hooks (trust gating) with a fix hint.

**Data & schema impact.** Version-range data consumed from N4; a preflight function in
`install.py`.

**Security & privacy.** Reads `claude --version` locally; no network.

**Edge cases.** `claude` absent → warn but allow `--no-daemon`/manual setup. Unparsable version →
warn. Version newer than tested → warn (not block).

**Dependencies.** N4 (matrix); `install.py`.

**Testing.** Old/missing/mismatched harness fixtures produce the right warning.

**Risks & mitigations.** Blocking a working newer harness (warn, never hard-block).

**Decision.** D-19.23 (warn vs block).

