# Design — Detector Evaluation & Public Corpus

**BLUF:** How detector effectiveness is measured and published honestly: an offline, deterministic eval harness over
a versioned public corpus grounded in academic agent-security benchmarks, with detector telemetry that lets
operators verify on their own data. **How** — the requirement is
[PRD 43](../prd/43-detector-credibility-and-evaluation.md) (DET-1..7, COR-1..4).

**Status:** proposed (2026-10-05, v0.2.0) · **Milestone:** M25–M26 · Sources:
[PRD 43](../prd/43-detector-credibility-and-evaluation.md), PRD 30 (analytics signals), PRD 38 (perf gate pattern),
PRD 29 (LLM explanation layer).

## Harness

- One command: `agentwatch detectors eval --corpus <version>` — offline, deterministic seeds, reproducible.
- Reports per-detector precision/recall (+ confidence intervals) and an aggregate, generated into
  `docs/reference/detector-catalog.md` (CI-guarded — docs-drift impossible).
- The eval harness **judges detectors**; detectors judge nothing, and the LLM stays out of the trust path
  (PRD 29/14). LLM detectors are evaluated by the same harness (local-model-first).

## Corpus v1 (COR-1)

- **Cases:** AgentDojo, InjecAgent, ASB, ATBench-Codex trajectories rendered into agentwatch record format
  (redacted, schema-valid) + the externalized 226 field-test scenarios + benign traffic for false-positive
  measurement. Shape-synthesized only — no copied secrets/PII.
- **Manifest:** per-case expected-verdict metadata (the Q6 `expected-verdicts.json` pattern); machine-checkable.
- **Vocabulary:** adopt the IETF BMWG `draft-han-bmwg-agent-security-benchmark` dimensions in the report (cheap
  standards alignment).
- **Versioning:** the corpus version is pinned in every published number; a new corpus release fails stale numbers
  (drift discipline).
- **License:** released open; sources cited per fixture.

## Detector telemetry (DET-5)

- Opt-in, local-only, content-free: fired/suppressed/false-positive markers per detector per window.
- Lets an operator (or their SIEM/ABA consumer) measure our detectors on *their* corpus (CUJ-19) and is feedable to
  the SIEM sinks ([PRD 44](../prd/44-identity-enterprise-and-compliance.md)).

## Injection & memory observations (DET-6..7)

- Deterministic heuristics over the MCP-recorded surfaces (resources/prompts/elicitation) and tool responses/args;
  emitted as anomaly events linking the source record; content-flow edges (S22) link source→sink without
  re-embedding content.
- High-false-positive rules ship **disabled by default**, with published precision/recall and an explicit opt-in.
- Memory read/write/delete recorded as observable surfaces + `search --memory` (closes the inherited G9 gap).

## Incident-registry interop (COR-2..4)

- Map detector findings/events to the **AIR** schema (architecture/mechanism/control/agency/outcome) and AIID's
  **GMF** taxonomy; optional incident tags on `annotate` (S20), metadata-only.
- `evidence <id> --include incident-report.json` emits a registry-shaped, redacted report; submission is a human
  act — a test proves no auto-egress path exists.
- Registry/postmortem mining (COR-4) is a standing practice: cited, shape-synthesized fixtures only.

## Non-goals

- Not an attack framework — public corpora are evaluation fixtures (agentdrill's lane is attack/eval).
- No submission anywhere by agentwatch; no registry-partnership claim without one.
