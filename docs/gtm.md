# Go-To-Market (pointer)

**BLUF:** agentwatch's GTM lives in the ecosystem set; this page points there.

- Release roadmap: ecosystem `strategy/01-release-roadmap.md`
- Design-partner program: ecosystem `gtm/01-design-partner-program.md`
- Demo scripts (Replit gate / poisoned tool / kill-switch): ecosystem `gtm/02-demo-scripts.md`
- Launch post (HN/README): ecosystem `gtm/03-launch-readme-hn.md`
- Content plan: ecosystem `gtm/05-content-plan.md`

**agentwatch-specific ask:** three demo sessions reproducible from the README, and a fresh-machine
≤15-minute recording proof.

## v0.2.0 GTM (proposed)

Positioning (one line): **agentwatch is the open, tamper-evident record layer for AI agents —
standards-native (OTel GenAI, IETF AAT, OCSF), local-first, and forensic-grade. Enforcement tools act; agentwatch
proves.**

Timing: EU AI Act Art. 12 procurement is live (staged Dec 2027/Aug 2028); SOCs are being rebuilt around agent
telemetry (Microsoft ISOC, Exabeam ABA, Menlo→Google SecOps); agent identity is a named national priority; and the
big clouds validated the category in Sept 2026 while leaving the tamper-evident/open-evidence/local-first gaps open.

Three launch stories (each demos <5 min, offline):

| Story | Features | CUJ | Buyer |
|---|---|---|---|
| "Your auditor accepts your agent logs" | AAT export + compliance reports + signed chain | CUJ-15/18 | Compliance |
| "Follow one action across every agent, host, and company" | trace correlation + identity + A2A | CUJ-16/20 | Security |
| "Every coding agent on the team, one honest record" | Cursor/Gemini/Codex fidelity + live watching | CUJ-17 | Platform engineering |

Adoption funnel: **try** (log-readers need no install) → **adopt** (Cursor hooks + Gemini recipe + `coverage`) →
**expand** (fleet + streaming + gateway spend) → **anchor** (AAT export, evidence bundles, compliance reports,
published detector numbers).

Ecosystem sequencing (wave-0): agentpolicy (events + ACS interop + streaming; AAT `record_phase` makes denials
provable) · agentdrill (export stability + unified SDK store + Cursor/Codex corpora) · agentcomply (provide
verifiable primitives, let it own the workflow).

Content plan: AAT implementation write-up (first-mover); "13M Cursor events, now with a hash chain" (vs Elastic's
datapoint); the Codex #36937 HOME-deletion postmortem as the untrusted-data case study; the detector-honesty post;
comparison-page refresh.

Metrics (opt-in/voluntary only; no silent telemetry — anti-metric unchanged): installs, reader-tier usage,
evidence/AAT exports, external adapter/reader PRs, detector reproduction rate.

Launch gate: the three stories demo offline; no "modeled" Tier-1 rows; AAT verified by an external third-party
consumer; claims ledger green; field-test report published; articles drafted.
