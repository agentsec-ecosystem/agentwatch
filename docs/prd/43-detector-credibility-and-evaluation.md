# PRD 43 — Detector Credibility & Evaluation

**BLUF:** Turn "43 detectors" from a claim into a measured fact: fix the 28 detectors that were silent on the
field-test corpus, publish per-detector precision/recall against a **public, versioned corpus** grounded in the
academic agent-security benchmarks, emit opt-in local detector telemetry, and add deterministic injection/memory
surface observations — all signals, never verdicts.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M27 ·
**Depends on:** PRD 30 (Analytics Signals), PRD 38 (Engineering Rigor), PRD 47 · **Extends:** L1 detector catalog

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **for a security product, published honesty is the brand.** "43 detectors" with 28 silent is a
claims-ledger liability; nobody in the open space publishes detector effectiveness, so doing it is a moat. The
LLM stays out of the trust path — the eval harness judges detectors; detectors judge nothing.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| DET-1..5 | Silent detectors fixed; per-detector precision/recall published; local telemetry | G4/G10: the count is a claim; every buyer asks "does this fire for us?" | CUJ-19 |
| COR-1..4 | Public eval corpus (grounded in AgentDojo/InjecAgent/ASB/ATBench) + registry export | no benchmark serves record-layer detection; registries lack structured evidence | CUJ-19, CUJ-8 |
| DET-6..7 | Deterministic injection + memory-surface observations | OWASP-top 2026 attack surfaces; inherited memory-audit gap (G9) | CUJ-8 (extended) |

**The "how" lives in design docs:** the eval methodology and corpus format in
[`design/detector-evaluation.md`](../design/detector-evaluation.md); injection/memory heuristics documented in the
extended [`reference/detector-catalog.md`](../reference/detector-catalog.md) (thresholds + false-positive risks —
also the maintenance-backlog ask).

### DET-1..5. Detector recall program + published effectiveness · v0.2.0 · (new)

**Why.** G4/G10 in the released limitations: 28/35 rule detectors were silent on the field-test corpus; the LLM
detectors were research-grade on a 10-trace sample. Every 2026 platform advertises "automatic insights"; the honest
answer to "does this fire for us?" is a published, reproducible number. Also feeds ABA/UEBA-class SOC consumers
(PRD 44 SIEM).

**Behavior.** **DET-1** an offline, deterministic, one-command eval harness (`agentwatch detectors eval`) + a
versioned public corpus. **DET-2** re-scope/rewrite the silent rule detectors against the field-test + v0.2.0
capture corpora; retire or reclassify with a reason. **DET-3** generate per-detector precision/recall into
`docs/reference/detector-catalog.md` (CI-guarded, docs-drift impossible). **DET-4** upgrade LLM detectors to the
same harness (local-model-first, PRD 29). **DET-5** opt-in local detector telemetry (fired/suppressed/false-
positive markers; redacted; feed-able — PRD 44).

**Data & schema impact.** New eval harness + catalog fields; detector output unchanged in shape.

**Security & privacy.** Telemetry is opt-in, local-only, content-free; no LLM in the trust path.

**Edge cases.** A detector firing only on synthetic data → retired, not kept for the count; high-FP rules →
disabled by default with explicit opt-in.

**Dependencies.** PRD 30 (L1 conventions), PRD 38 (perf/claims-ledger patterns), PRD 47 (corpus/replay).

**Testing.** Corpus reproduction is deterministic; ≥80% of rule detectors non-silent; a detector without a catalog
entry fails CI; claims-ledger entries present.

**Risks & mitigations.** Numbers that do not generalize → publish corpus + method + confidence intervals + a
"your corpus may differ" statement; DET-5 lets evaluators verify locally.

**Decision.** ADR-0017 (sampling/telemetry) — what detector telemetry records and its gating.

### COR-1..4. Public eval corpus + incident-registry interop · v0.2.0 · (new)

**Why.** DET-1 needs a corpus; the 2026 benchmark audit ("Talk is Not Cheap") shows the major benchmarks cover
≤25% of the attack-type matrix and none serves *record-layer* detection. Incident registries (AIID, the Agent
Incident Registry/AIR) explicitly lack structured evidence (AAAI "Incident Analysis for AI Agents", 2026) —
exactly what agentwatch produces.

**Behavior.** **COR-1** assemble and publish the corpus v1: render AgentDojo/InjecAgent/ASB/ATBench-Codex cases
into record format (redacted, schema-valid) + externalize the 226 field-test scenarios + benign FP traffic, with a
per-case expected-verdict manifest (Q6 pattern); adopt the IETF BMWG agent-security-benchmark draft vocabulary in
the report. **COR-2** map detector findings/security events to the AIR schema (architecture/mechanism/control/
agency/outcome) and AIID GMF taxonomy; optional incident tags on `annotate` (S20). **COR-3**
`evidence <id> --include incident-report.json` — a registry-shaped, redacted, voluntary export (no auto-egress;
test proves it). **COR-4** registry/postmortem mining into cited, shape-synthesized fixtures (standing practice).

**Data & schema impact.** Corpus + optional annotation tags + an export; no record-schema change.

**Security & privacy.** Corpus carries no real secrets/PII (governance scan); submission is a human act.

**Edge cases.** A benchmark case that does not map cleanly → excluded with a reason; a new corpus release fails
stale published numbers (drift).

**Dependencies.** DET-1, PRD 31 (annotate/evidence), PRD 18 (S20).

**Testing.** Corpus licenses recorded; per-case verdicts machine-checkable; COR-3 validates against a schema
fixture; no auto-submission path exists.

**Risks & mitigations.** Over-claiming registry adoption → schema-shaped export only; adoption is theirs to confirm.

**Decision.** ADR — corpus licensing and the corpus-version-in-every-number rule.

### DET-6..7. Injection & memory-surface observations · v0.2.0 · (new)

**Why.** Prompt injection and agent memory are the two most-funded 2026 attack surfaces (OWASP Agentic SDLC;
"memory forensics" modules at runtime-security vendors). agentwatch inherited "no memory-audit" (G9) and has no
injection signal — a record layer that cannot show these surfaces is blind to the incidents the industry is having.

**Behavior.** **DET-6** deterministic heuristic detectors for injection-shaped content in tool responses/args/
resources/prompts (the B3/MCP-recorded surfaces): instruction-override patterns, hidden-instruction markers,
abnormal imperative density — anomaly events linking the source record; **signals, never verdicts**. **DET-7**
agent memory reads/writes/deletes as observable records + `search --memory`.

**Data & schema impact.** New anomaly/memory records; content redacted per privacy mode, metadata always.

**Security & privacy.** No enforcement (classification-as-boundary is a non-goal, PRD 14); high-FP rules off by
default; content-flow edges (S22) link source→sink without re-embedding content.

**Edge cases.** A memory path outside the project → attributed but flagged; injection heuristic with high FP →
disabled by default.

**Dependencies.** DET-1 (precision/recall), S22 (content-flow), PRD 42 (B3/MCP surfaces).

**Testing.** Published precision/recall for the heuristics; memory events respect privacy modes; CUJ-8 extended
(`replay --anomalies`).

**Risks & mitigations.** Read as enforcement → hard rule: observations only; leave scoring to agentpolicy.

**Decision.** D-43.x — injection heuristic set + default off/on list.
