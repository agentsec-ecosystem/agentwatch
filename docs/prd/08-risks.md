# PRD 08 — Risks

**BLUF:** The hard parts are **harness surface area** and **the standards play**, not the recording itself.
Each risk below has a concrete mitigation and an owner-facing trigger.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Risks

| # | Risk | Likelihood | Impact | Mitigation | Trigger to act |
|---|---|---|---|---|---|
| R1 | **Cursor/Codex expose too little surface** for full-fidelity recording | Medium | Harness coverage promise | Document gaps honestly; proxy-interposition where hooks are insufficient; lower-layer coverage via OTel/eBPF | Cursor adapter can't capture a CUJ-relevant event class |
| R2 | **OTel GenAI semconv is Development-grade** and may churn | Medium | Format stability | Track upstream; version the schema; contribute rather than fork (`DD-05`) | Upstream breaking change to `execute_tool` spans |
| R3 | **Schema stewardship** — alone vs the OTel working group | Medium | Adoption vs control | Decide in v0.1.0; lean to propose upstream if it materially increases adoption | Schema v1 ready to publish |
| R4 | **Privacy / secret leakage** in records | Low | Trust (binary) | Redaction-by-default + attack-pack verification in CI (R7) | Attack pack finds any leak |
| R5 | **Fail-open** — recording silently stops | Medium | False confidence | Fail-closed on tamper + daemon health surfaced | Tamper test or health check fails |
| R6 | **Schema overfitting to one runtime** (the AgentObservatory lesson) | Medium | Portability | Model the schema from real sessions; formalize the contract **before** the detector catalog | A field only makes sense for Claude Code |
| R7 | **Trying to solve too much** — analytics/eval/policy in this repo | Medium | Focus | Strict non-requirements; enforcement/alerting/eval are other tools | A PR adds a detector or alert path |
| R8 | **Single-maintainer fragility** | High | Adoption/enterprise trust | Governance ladder; recruit a second maintainer (P0) per org governance | First public release with one maintainer |
| R9 | **"Yet another observability tool" sameness** | Medium | Differentiation | Lead with the **security-event schema**, not the trace viewer | Messaging drifts to dashboards |
| R10 | **Migration pain for agent-exec-trace users** | Low | Existing users | Publish a schema mapping; archive the old repo with a pointer | Any active issue reports a migration gap |

## Hard parts (be explicit)

- **What counts as meaningful behavior.** Too little instrumentation and records are useless; too much and
  operators drown. The AgentObservatory lesson: formalize the trace contract first.
- **Signal vs noise.** Agent workloads change constantly; a 3× cost change may be a problem or harder work.
  agentwatch's answer: **record it and expose it; let policy/alerting judge it.**
- **Cross-harness correlation.** W3C Trace Context must survive hooks, proxies, and MCP hops.

## Governance link

Kill criteria and pivots live in the ecosystem governance set
(`training/research/agent-security/ecosystem/governance/02-kill-criteria-pivots.md`).

---

## Build risks (BR1–BR7)

Risks specific to *building* v0.1.0 (distinct from the product risks above). Each has a mitigation and a trigger.

| # | Risk | Mitigation | Trigger |
|---|---|---|---|
| BR1 | Claude Code hook API shape changes mid-build | Pin to a documented version; abstract the event in the adapter; revisit at build start | Claude Code releases a hook change |
| BR2 | OTel GenAI semconv churns mid-build | Track upstream; version our schema; propose upstream early (DD-05) | Upstream breaking change to `execute_tool` |
| BR3 | Hash-chain fsync dominates the perf budget | Batch fsync (group commits); benchmark early in M3 | p99 > 5 ms in perf test |
| BR4 | Redaction regex perf or false negatives | Pre-compile regex; attack pack in CI; corpus grows | Attack pack finds a leak |
| BR5 | Parity work pulls scope into v0.1.0 | v0.1.0 is foundation only; parity lands v0.2.0–v1.0 (PRD 05/09) | A PR adds a detector or UI to v0.1.0 |
| BR6 | Single-maintainer bottleneck | Governance ladder; recruit a second maintainer (P0) | Any release gate blocked on one person |
| BR7 | Local socket perms / multi-user issues | Per-user socket path; document single-user v0.1.0 | Multi-user bug report |
