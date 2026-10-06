# PRD 59 — OWASP Agentic & Standards Coverage

**BLUF:** Publish where the record can and cannot evidence each agentic risk, in the vocabulary security buyers now
use — **OWASP Top 10 for Agentic Applications 2026 (ASI01–ASI10)** plus the **Agentic Skills Top 10** — as a
`compliance report` framework; and commit to a standards-participation plan (closing the open DD-05) so the open
security-event schema and authorization taxonomy are proposed upstream rather than only owned locally.

**Status:** proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27 (ASI),
M30/governance (STD) · **Depends on:** PRD 39 (W1/W2), PRD 44 (CMP-1/2), PRD 49 (APV), PRD 52 (CAP), PRD 43 (DET-7) ·
**Extends:** compliance matrix (OWASP **LLM** Top-10 only today), DD-05 · **Adds:** CUJ-18 extension

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **a coverage map is honest or it is marketing.** Every row cites evidence the record can regenerate, or
states plainly that the record cannot evidence that risk.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| ASI-1 | `compliance report --framework owasp-asi-2026` (+ AST10) | Security buyers use the ASI vocabulary; vendors publish coverage tables; cheap, high-credibility | 18 (ext.) |
| STD-1 | Standards participation plan; close DD-05; track submissions | The moat requires being *in* the rooms; drafts are churning | — |

## ASI-1 — OWASP Agentic coverage map · (new)

**Why.** The OWASP Top 10 for Agentic Applications 2026 (ASI01 Goal Hijack … ASI10 Rogue Agents) is the peer-reviewed
framework buyers cite; a dedicated Agentic Skills Top 10 exists; vendors (e.g. Microsoft's Agent Governance Toolkit)
publish per-risk coverage ("full/partial/gap"). agentwatch's matrix maps only OWASP **LLM** Top-10 2025 (LLM01/02/05/06).

**Behavior.** A framework template that, for each ASI risk (and the AST10 section), states: what the record evidences,
the command that regenerates it, what it **cannot** evidence, and the fidelity tier.

**Acceptance.**
- [ ] All ten rows present; each has an evidence command or an explicit "not evidenced"; nothing claims prevention.
- [ ] Rows link to features: ASI03→IDN; ASI04→CAP (52); ASI06→DET-7/MEM (52); ASI07→A2A/TRACE; ASI09→APV-3 (49);
      ASI01/ASI05→content-flow/DET-6/cls1 (as signals) (FT-ASI-1).
- [ ] Included in the executable-docs gate (every row's command runs in CI).
- [ ] Carries the non-certification statement (W1 discipline).

**Security & privacy.** Read-only report; no new exposure.
**Dependencies.** CMP-1/2, APV-3, CAP, DET-7.
**Risks & mitigations.** Read as certification → explicit non-conformity statement. **Decision.** D-59.x — row evidence map.

## STD-1 — Standards participation plan · (governance)

**Why.** The moat is "the open security-event schema becomes the default", which requires contributing to OTel GenAI
semconv (security-event conventions), the IETF AAT draft, Agent Trace, OCSF and OWASP Agentic. DD-05 ("solo steward vs
propose into OTel from day one") is still open; drafts churn (AAT -06, Agent Trace v0.1 RFC).

**Behavior.** A published plan and owner: target specs, what is proposed (event vocabulary, authorization taxonomy v2
from PRD 49, `capability-changed`), and a quarterly re-pin/engagement cadence.

**Acceptance.**
- [ ] DD-05 closed with a decision + rationale.
- [ ] ≥1 upstream contribution per target spec by the release gate (issue/PR/draft comment), tracked in the claims ledger
      as "submitted", never "adopted".
- [ ] External adopter count tracked (PRD 07 metric: ≥1 non-ecosystem consumer of each export).

**Dependencies.** Schema stewardship, ADR-0027.
**Risks & mitigations.** Over-claiming adoption → ledger wording. **Decision.** ADR-0045.

## Not goals
Scoring risk; certifying; recommending controls beyond pointing to agentpolicy/agentdrill; claiming adoption.

## Sources
genai.owasp.org (ASI 2026; Agentic Skills Top 10); github.com/microsoft/agent-governance-toolkit compliance docs;
IETF AAT draft; agent-trace.dev; OCSF. Local analysis files 04, 07, 10.
