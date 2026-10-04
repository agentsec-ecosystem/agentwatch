# PRD 39 — Standards & Compliance Acceptance

**BLUF:** Make the compliance story answerable by a buyer, an auditor, and an opposing expert: an EU AI Act
record-keeping mapping, real ISO/NIST appendices, adoption of the open artifact standards, a pinned OTel
semconv version, published schema stewardship, a forensic-soundness statement, optional checkpoint
notarization/signing, and OpenSSF/OSV readiness.

**Status:** shipped (2026-10-03) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M22

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

The through-line: **we are a mechanism that helps you meet an obligation, not a certification.** Every mapping
below pairs each claimed control with the command or test that evidences it and states what we do *not*
provide.

### W1. EU AI Act record-keeping mapping (Art. 12, Art. 19, Art. 26) · v0.1.0 · (new · biggest single gap)

**Why.** Article 12 requires high-risk AI systems to **automatically record events over their lifetime**;
Article 19 governs log retention; Article 26 puts a logging duty on deployers. agentwatch *is* an implementation
of that obligation — automatic, tamper-evident, retained, exportable — and PRD 18 never mentions it. Any EU
enterprise buyer asks about Art. 12 before anything else, and "we are a mechanism that helps you meet it, here
is the control mapping" is a true, provable, honest claim (and emphatically not a conformity claim).

**Behavior.** An appendix mapping Art. 12/19/26 obligations → agentwatch controls → the test or command that
evidences each, with an explicit "what we do not provide" section (risk management, conformity assessment,
human oversight — other tools, other projects). Pairs naturally with the evidence bundle (S1) as the deliverable
artifact.

**Data & schema impact.** Docs mapping; no product change.

**Security & privacy.** None; must not overclaim conformity.

**Edge cases.** An obligation partially met → listed with the gap named; a change in the articles → the mapping
is versioned with the regulation date.

**Dependencies.** PRD 18, S1, E1 retention (Art. 19).

**Testing.** Link-check; every mapped control names a command/test; the "do not provide" section is present.

**Risks & mitigations.** Read as a conformity claim → explicit non-conformity statement in the mapping and the
docs.

**Decision.** New — mapping granularity and the "do not provide" boundary.

### W2. Make the ISO/IEC 42001 and 27001 appendices real · v0.1.0 · (new)

**Why.** PRD 18 lists ISO/IEC 42001 as "controls-mapping appendix" — promised, not written. Add **ISO/IEC 27001
Annex A.8.15 (logging)** and **A.8.16 (monitoring activities)**, the clauses an auditor will actually open, and
**NIST SP 800-92** (log management) for the operational shape.

**Behavior.** One table per standard: clause → control → agentwatch feature → evidence command.

**Data & schema impact.** Docs only.

**Security & privacy.** None.

**Edge cases.** A clause with no direct feature → listed as "not applicable / elsewhere," never omitted.

**Dependencies.** PRD 18, W1.

**Testing.** Link-check; every row names an evidence command that exists.

**Risks & mitigations.** Rows drifting from features → evidence commands are executable (Q10).

**Decision.** New — which clauses are in scope for v0.1.0.

### W3. Align with the open artifact standards instead of inventing shapes · v0.1.0 · (new)

**Why.** Three standards fit agentwatch's outputs exactly and cost a transcode each: **OCSF** for security
events (S8), **CloudEvents** for the event-interchange envelope (B2/S10), **CycloneDX** for the BOM (S9). Each
replaces "trust our JSON" with "here it is in the format your tooling already parses" — strengthening PRD 00's
"no proprietary formats" promise.

**Behavior.** Adopt the three standards as the export/mapping targets; pin each version in output; document the
"lossless-or-explicit" rule.

**Data & schema impact.** Three export formats/mappings; agentwatch's schema stays the source of truth.

**Security & privacy.** Export only, opt-in, open standards.

**Edge cases.** A field a standard cannot express → surfaced, never dropped; a standard version bump → pinned
and tested.

**Dependencies.** S8, S9, S10, B2, PRD 00.

**Testing.** Each output validates against its pinned standard schema; unmapped fields are reported.

**Risks & mitigations.** Standards churn → pin versions + conformance tests.

**Decision.** New — the version pins and the "lossless-or-explicit" rule.

### W4. Pin and publish the OTel GenAI semconv version, and upstream · v0.1.0 · (new)

**Why.** `01-why.md:14` identifies the exact problem — GenAI semconv is **Development-grade and moving** — and
makes "just works OTel GenAI" a headline claim. A moving target under a stability claim is a support burden and
a credibility risk if a user's backend disagrees with ours.

**Behavior.** (a) State the pinned semconv version in docs, in `--version`, and in exported resource attributes;
(b) a CI job that diffs against upstream and opens an issue on drift; (c) propose the security-event vocabulary
into OTel GenAI (`DD-05`'s open question) — being the *proposer* of the convention is worth more than being its
sole steward.

**Data & schema impact.** Pinned semconv constant + CI drift job; no record change.

**Security & privacy.** None.

**Edge cases.** Upstream drift → an issue, not a silent break; an unmappable attribute → reported.

**Dependencies.** M5 export, S39, DD-05, R4.

**Testing.** Exported resource attributes carry the pinned version; the drift job opens an issue on a simulated
change.

**Risks & mitigations.** Pinning too early → pin + document the policy for moving it.

**Decision.** New — the pinned version and the drift-job cadence.

### W5. Schema stewardship as published policy · v0.1.0 · (new)

**Why.** R5's thesis is "first to ship the convention becomes the default," and defaults are won on governance,
not JSON. Today `schema/` is machine-readable but the policy around it is not stated — and S4 wants a sixth
event type, the moment the policy either exists or is improvised.

**Behavior.** Resolvable `$id` URLs; a semver policy (additive minor / breaking major with a deprecation
window); a changelog per schema; a documented proposal process for new event types; a listing in a public
registry (SchemaStore); and a **conformance suite for emitters and consumers** — the third-party-facing peer of
O1's adapter runner.

**Data & schema impact.** Policy + a schema conformance suite; no record change.

**Security & privacy.** None.

**Edge cases.** A new event type → follows the published process (S4 is the first test of it); an unknown
version → rejected with the supported range named.

**Dependencies.** R5 schema, S4, J1, O1, Q6.

**Testing.** A schema change without a changelog entry fails the policy check; an emitter/consumer suite case
passes or fails explicitly.

**Risks & mitigations.** Policy written but unenforced → CI checks the changelog/version rules.

**Decision.** New — the proposal process and whether S4 lands only after W5 publishes the process.

### W6. A forensic-soundness statement · v0.1.0 · (new)

**Why.** PRD 18 §C's "what we do not claim" is excellent on ML and certification, and silent on evidence
handling — yet "forensic evidence" (`18:66`) is exactly the claim an opposing expert would attack. Using the
established vocabulary (**NIST SP 800-86**, **ISO/IEC 27037**) and stating the limits precisely separates a tool
an investigator will rely on from one they will not.

**Behavior.** One page: what the chain proves (append-order integrity, no undetected in-place edit); what it
does **not** (an operator with disk access can rewrite the whole chain before any checkpoint is anchored;
absence of a record is not proof of absence of an action); how checkpoints (E1) and coverage windows (S5) narrow
those gaps; and the recommended handling procedure for a bundle.

**Data & schema impact.** Docs; shipped inside the evidence bundle (S1) and the threat model.

**Security & privacy.** None; must give ground honestly.

**Edge cases.** A bundle without anchors → the statement says so; a bundle with a gap → stated on the front
page.

**Dependencies.** PRD 06 threat model, E1, S1, S5, S2.

**Testing.** Link-check; the statement's claims map to S1/W6 sections; it ships in the bundle.

**Risks & mitigations.** Understating the guarantee hurts adoption, overstating kills credibility → reviewed
against the actual chain properties.

**Decision.** New — the exact set of "does not prove" limits.

### W7. Optional checkpoint notarization — the honest version of what blockchain was rejected for · v0.1.0 · (new)

**Why.** PRD 14 rightly rejects blockchain anchoring as theater, and PRD 21 notes checkpoints "offer no natural
anchor point for evidence stored off-machine." The real need — *prove the chain existed in this state at time
T* — has a boring standard answer: **RFC 3161** timestamping, or publishing the checkpoint digest somewhere
append-only the operator already trusts.

**Behavior.** `agentwatch checkpoint export` emitting a digest + optional RFC 3161 token from an
operator-configured TSA (off by default, explicit opt-in — identical gating to export), plus documented
zero-infrastructure options (commit the digest to git, email it to yourself).

**Data & schema impact.** New command + optional token; reuses E1 checkpoints.

**Security & privacy.** Opt-in egress (only when a TSA is configured), same gate as OTLP export (R6/DD-09).

**Edge cases.** TSA unreachable → the digest is still exported, the token omitted with a note; no TSA configured
→ digest-only.

**Dependencies.** E1, DD-09, W9.

**Testing.** `checkpoint export` emits a digest; with a configured TSA, a token is attached; without one, the
export still succeeds and states digest-only.

**Risks & mitigations.** Becoming a trust dependency → off by default; zero-infrastructure options documented.

**Decision.** D-31.6 — TSA opt-in and the digest-publishing options.

### W8. OpenSSF Best Practices badge (gold path) and OSV/advisory readiness · v0.1.0 · (new)

**Why.** PRD 18 §D targets Scorecard grade A; the **OpenSSF Best Practices badge** is the other half of the pair
and the one humans actually look at on a README. Most criteria are already met (license, DCO, CODEOWNERS,
SECURITY policy, tests, static analysis).

**Behavior.** Complete the passing tier before v0.1.0 and display it; register with OSV; document the advisory
flow end to end (PRD 18 names it; prove it with a dry run).

**Data & schema impact.** Governance/repo metadata; no product change.

**Security & privacy.** None.

**Edge cases.** A criterion partially met → listed with the gap; badge metadata drifting → checked at the release
gate.

**Dependencies.** PRD 18 §D, Scorecard workflow, release gate (Q13).

**Testing.** The badge self-assessment is complete; a dry-run advisory produces the documented flow.

**Risks & mitigations.** Badge achieved then abandoned → release-gate re-check.

**Decision.** New — passing vs gold target for v0.1.0.

### W9. Optional signed checkpoints · v0.1.0 · (new)

**Why.** Hash chains give integrity, not origin. A local ed25519 signature over checkpoints adds
non-repudiation — "this checkpoint was produced by this installation" — which turns a bundle from "internally
consistent" into "attributable." The key-management objection that correctly killed encryption-at-rest (PRD 14)
is much weaker here: a signing key that only ever signs digests has no recovery problem (lose it and you start
a new key epoch; nothing becomes unreadable).

**Behavior.** Opt-in, OS-keychain-backed, key id recorded in checkpoints and bundles, documented as
"attributable to this installation" and never as "attributable to this human."

**Data & schema impact.** New optional signature on checkpoints/bundles; no record change.

**Security & privacy.** Local key, no egress; key id is metadata; documented precisely.

**Edge cases.** Key lost → a new epoch; bundles state which key epoch signed them; verification without the key
→ reports "signed by key id X, key unavailable."

**Dependencies.** E1, W7, S1, S12.

**Testing.** A signed checkpoint verifies with its public key; a tampered one fails; a missing key reports
unavailable rather than invalid.

**Risks & mitigations.** Overclaiming origin → docs say "this installation," not "this human."

**Decision.** New — key storage (OS keychain) and epoch semantics.
