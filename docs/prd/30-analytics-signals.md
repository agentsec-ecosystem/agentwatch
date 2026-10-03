# PRD 30 — Analytics Signals

**BLUF:** Purpose-built anomaly signals for Claude Code hook records — observability only, never
enforcement — complementing the 40 ported framework detectors.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before
> storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or
> chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress
> without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5);
> conformance and quality gates apply (NFR-11).

### L1. Claude-Code-specific detector starter pack · M6 · #210

**Why (evidence).** The 40 ported detectors target framework traces (LangGraph runs). Claude Code
hook records have their own obvious failure shapes that no detector names yet: tool-retry loops,
denied-call clusters, file-write storms, network-tool patterns (`curl`/`wget`), and
session-duration outliers. PRD 14 keeps these as *signals* — observability, not enforcement — a
boundary that is already policy.

**Behavior.** A small starter set of rule detectors purpose-built for hook records, wired into the
M6 pipeline with documented thresholds, each producing an anomaly with `severity`, `explanation`,
and `evidence` (the existing analytics shape). Examples: `tool-retry-loop` (same tool/args
repeated ≥N times in a window), `denied-cluster` (≥N denials in a session), `write-storm` (many
file-write tools in a short window), `network-tool` (curl/wget usage flagged for review),
`session-duration-outlier` (beyond a trailing baseline).

**Data & schema impact.** New rule definitions in the M6 detector registry (with the ported 40);
thresholds in config; consumes `outcome=denied` (A2), `step_type=reason` (A3), and `tool.server`
(D1) where relevant.

**Security & privacy.** Detectors read already-redacted stored records only; no raw content; no
enforcement action (signals only — PRD 14). The LLM-augmented detectors already in M6 remain
signals, not controls.

**Edge cases.** Low-volume sessions (avoid firing on N<min); timezone/clock skew in windows (B5);
retry loops that are legitimate (thresholds documented and tunable); a detector firing on imported
history (H1) should not re-alert historically without an explicit `--since`.

**Dependencies.** M6 analytics pipeline (parity); A2/A3/D1 for the signal inputs; B5 for windows.

**Testing.** Each detector fires on a crafted fixture and stays silent on benign data (including
the low-volume and legitimate-retry cases); thresholds are documented; a mutation check that the
detector cannot pass vacuously.

**Risks & mitigations.** False-positive noise (documented thresholds + tunable + low-volume
guards). Scope creep into enforcement (PRD 14 boundary restated).

**Decision.** D-19.40 (threshold defaults + whether detectors run on imported history).
