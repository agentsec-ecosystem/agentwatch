# Field-Test Plan — agentwatch v0.2.0

**BLUF:** The v0.2.0 field-test plan (M25 **25.FLD-1a**, PRD 40 §5). It fixes the case roster now so
execution (M29) is a matter of running, not deciding. Cases are grouped by the v0.2.0 capability and the
CUJ they prove; each names its owning ticket, harness, evidence, and pass condition.

**Status:** draft (2026-10-05) · **Milestone:** M25 (plan) → M29 (execution) · Sources:
[PRD 40](../../prd/40-v0.2.0-program.md) §5, [PRD 07](../../prd/07-success-metrics.md),
[PRD 43](../../prd/43-detector-credibility-and-evaluation.md),
[PRD 47](../../prd/47-cross-harness-testkit.md), [PRD 04](../../prd/04-users-and-cujs.md) (CUJ-15–20).

## Environments

| Env | Purpose | Notes |
|---|---|---|
| `local-macos` | Primary developer run | Claude Code + Cursor installed |
| `local-linux` | Windows/Linux parity, system-effects | opt-in ingest |
| `ci-hermetic` | Deterministic replay, no network | pins models, uses fixtures |
| `clean-machine` | First-run ≤15 min (M30 30.9) | timed from zero |

## Case roster

| ID | Capability | CUJ | Owning ticket(s) | Harness | Evidence | Pass condition |
|---|---|---|---|---|---|---|
| FT-AAT-1 | AAT export → third-party round-trip | CUJ-15 | AAT-1..5 | claude-code | `export-session --format aat` bundle | External AAT consumer validates + chain verifies |
| FT-AAT-2 | Foreign AAT ingest + quarantine | — | AAT-3 | synthetic bundle | quarantine log | Non-normalizable records quarantined with a reason |
| FT-TRACE-1 | One causal chain across agents/hosts | CUJ-16 | TRACE-1/2 | 3 hosts / 3 harnesses | `trace <tid>` tree | One ordered chain; broker gaps classified |
| FT-LIVE-1 | Live view p99 ≤ 1 s | CUJ-17 | STR-1..3 | claude-code + daemon | timeline + `degraded` state | hook→view p99 ≤ 1 s; no store loss on consumer crash |
| FT-CMP-1 | One-command compliance report | CUJ-18 | CMP-1/2 | offline | eu-ai-act-art12 report | Every row regenerable; zero unverifiable claims |
| FT-DET-1 | Detector effectiveness reproduced | CUJ-19 | DET-1..5, COR-1 | public corpus | `detectors eval` output | Deterministic reproduction; ≥80% rule detectors non-silent |
| FT-DET-2 | Injection/memory observations | — | DET-6/7 | injection corpus | memory/injection records | Observations fire with published precision/recall |
| FT-IDN-1 | Attribution end-to-end | CUJ-16 | IDN-1..4 | multi-agent fixture | `impact`/`blame`/`tree`/`trace` | Full attribution answered in one command |
| FT-A2A-1 | Cross-org delegation provable | CUJ-20 | A2A-1/2 | A2A proxy | signed agent-card provenance | Unverified cards recorded, never trusted as authorization |
| FT-MCP-1 | MCP 2026-07-28 surface | — | MCP-1..6 | MCP server | tool/resource/prompt records | New transport; blocking events never answered |
| FT-HARNESS-1 | Cross-harness fidelity tiers | — | XHT-1..4 | all registered adapters | compatibility matrix | No "modeled" Tier-1 rows; each row carries a live/fixture tier |
| FT-GEM-1 | Gemini native-OTel ingest | — | GEM-1/2 | Gemini CLI | ingested records | Telemetry ingests; logPrompts path redacted |
| FT-CUR-1 | Cursor authenticated capture | — | CUR-1..3 | Cursor IDE | golden fixtures | ≥2 version-tagged sets; no unexplained coverage gap |
| FT-GWY-1 | Gateway OTel ingest + cost | — | GWY-1/2 | LiteLLM | records + cost | Exact vs estimated cost distinguished |
| FT-SIEM-1 | OCSF/Syslog event stream | CUJ-18 | SIEM-1/2 | reference consumer | OCSF stream | Conformance-tested; OCSF 1.5.0 |
| FT-SIGN-1 | Signed default posture | — | CMP-4 | checkpoint | ed25519 signature | Verify succeeds; unverifiable is never ok |
| FT-WIN-1 | Windows support | — | WIN-1 | Windows CI | test run | Suite green on Windows |

## Evidence & report

- Every case emits an artifact under `field-test/v0.2.0/results/` (raw output + environment fingerprint).
- The M29 report (`docs/field-test/v0.2.0/FIELD_TEST_REPORT.md`) assembles per-case verdicts, the
  compatibility matrix, and the claims-ledger check.
- A case that cannot pass is recorded with an explicit, named limitation — never dropped silently.

## Out of scope (declared)

Enforcement, attack/eval frameworks, hosted SIEM, prompt analytics, injection classification as a security
boundary (PRD 14, unchanged). Phased items (PG, TSS, DET-6/7, CMP-3/4, OTEL-4, COR-2..4) are tested only if
they land in v0.2.0; otherwise they carry forward by name.
