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
