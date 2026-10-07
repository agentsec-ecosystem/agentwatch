# ADR-0045 — Standards participation

- **Status:** accepted (2026-10-06)
- **Context:** [DD-05](../design/design-decisions.md) ("solo steward vs propose into OTel from day one") was
  still open: we accepted that improvements go upstream, but had no published owner, target set, or cadence.
  The surrounding drafts churn (IETF AAT `-06`, Agent Trace v0.1 RFC, OTel GenAI semconv Development-grade,
  OCSF 1.5.0), so "contribute" has to be an operating commitment, not an intention. PRD 59 §STD-1 closes it.
- **Decision:** Publish a **standards participation plan** (owner: the schema steward) covering five target
  specs — OTel GenAI semconv, IETF AAT, Agent Trace, OCSF, and OWASP Agentic. We propose our **event
  vocabulary**, **authorization taxonomy v2** (PRD 49 / ADR-0027), and **`capability-changed`** (PRD 52)
  upstream. Contributions are tracked in the claims ledger as **"submitted"**, never "adopted"; we keep a
  repo-local copy until a spec adopts them. Engagement runs on a **quarterly re-pin/engagement cadence**, and
  drift checks fail CI when an upstream revision moves without a reviewed pin. DD-05 is **closed** by this
  decision; ADR-0005's "propose upstream, do not fork" direction is unchanged.
- **Consequences:** The plan is executable and auditable ([reference/standards-participation.md](../reference/standards-participation.md));
  wording discipline is enforced by the ledger check. Participation is engagement, not endorsement — the plan
  never claims adoption, conformance, or certification. No forking; a repo-local copy remains the source of
  truth until (and if) a spec adopts a proposal.
