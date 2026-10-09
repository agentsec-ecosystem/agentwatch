# PRD 44 — Agent Identity, Enterprise & Compliance

**BLUF:** Answer the question that currently has no answer — *which non-human entity, under which credential, on
whose behalf, with whose approval* — with a first-class **agent identity** dimension aligned to IETF AIMS/WIMSE, and
convert the shipped compliance mappings into **one-command, offline-verifiable framework reports**, with managed
retention, a signed default posture, and hardened SIEM sinks.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0 (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M25–M27 ·
**Depends on:** PRD 35 (Capture Context), PRD 39 (Standards & Compliance Acceptance), PRD 18 (Security &
Compliance), PRD 31 (Evidence) · **Extends:** S14 approval provenance, W1–W9

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **only the record layer can attribute an action to a non-human entity** — no SIEM can attribute what
the telemetry never carried. Identity is the #1 stated governance gap (NIST/CAISI AASI, NCCoE, CSA: 90% of agents
over-permissioned, >75% of orgs lack agent-identity policy); recording it is inherently ours; enforcing it stays
agentpolicy's.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| IDN-1..4 | `agent_identity` + delegation chain on records; attribution end-to-end | G11; the #1 stated governance gap; AAT requires the fields; ABA consumers need identity on events | CUJ-14 (completed), CUJ-16 |
| CMP-1..4 | One-command offline compliance reports; retention profiles; signed default | G12; "one-click reports" is category table stakes; Art. 12 procurement is now; G8 | CUJ-18 |
| SIEM-1..2 | Conformance-tested OCSF event stream + Syslog sink | SOCs rebuild around agent telemetry; ingestion economics favor lean events | CUJ-18, CUJ-16 |

**The "how" lives in design docs:** identity field set + hashing in
[`design/agent-identity.md`](../design/agent-identity.md); report/retention mechanics in
[`design/forensic-soundness.md`](../design/forensic-soundness.md) and [`compliance/`](../compliance/); sink
mechanics in [`design/observability.md`](../design/observability.md).

### IDN-1..4. Agent identity & delegation records · v0.2.0 · (new)

**Why.** Records answer "what happened," not "which agent identity, under whose delegation." IETF AIMS
(WIMSE+SPIFFE+OAuth) is standardizing the vocabulary; AAT requires the fields; two-layer model: transport (WHO is
calling — workload identity) + application (ON WHOSE BEHALF — delegation chain). G11.

**Behavior.** **IDN-1** an `agent_identity` dimension on records: agent name/version, harness, model, workload-
identity ref (SPIFFE/WIMSE URI when present), credential class (api-key | oauth | svid | ambient/shared).
**IDN-2** delegation-chain capture (on-behalf-of) where the harness exposes it; `search --identity`.
**IDN-3** attribution rendered end-to-end in `impact`/`blame`/`tree`/`trace`. **IDN-4** a credential-hygiene
observation (shared/ambient credential flag — NIST's pre-Q4-2026 audit ask) + published mapping to
AIMS/WIMSE/NCCoE.

**Data & schema impact.** Additive identity fields; AAT export populated (PRD 41); never secret material.

**Security & privacy.** Hashed by default in metadata-only mode; property test: identity fields never contain
secret material; operator consent for plaintext identity (mirrors `full` privacy mode).

**Edge cases.** Harness exposes no delegation → honest `unknown` (S14 discipline); same agent, multiple workload
instances → distinguished by identity ref.

**Dependencies.** S14, PRD 35 (OS principal S29), PRD 41 (AAT), PRD 43 (precision/recall for the hygiene flag).

**Testing.** A synthetic multi-agent scenario answers attribution in one command; identity fields pass the secret
property test; the hygiene observation fires on a fixture corpus with published precision/recall.

**Risks & mitigations.** Surveillance surface → hashed default + consent; overclaiming → "attributable to this
installation," never "this human."

**Decision.** ADR-0020 — field set, hashing policy, AIMS alignment, honest-unknown rules.

### CMP-1..4. One-command compliance reports, retention, signed default · v0.2.0 · (new)

**Why.** "One-click compliance reports" is advertised category-wide; we have the inputs (compliance matrix,
evidence bundles, chain, retention) but no single command. EU AI Act Art. 12 application is staged Dec 2027/Aug
2028 — procurement is now. G12 + the released ed25519 checkpoints being opt-in/unreleased (G8).

**Behavior.** **CMP-1** `agentwatch compliance report --framework … [--period] [--out DIR]`: control → evidence
command → verdict → bundle refs → retention/signature status; every row regenerable.
**CMP-2** templates eu-ai-act-art12, iso-42001, iso-27001, soc2, nist-800-92 (from the W1–W2 mappings).
**CMP-3** policy-driven retention profiles (`high-risk-12mo` per AAT §9, `general-6mo`, custom) driving the shipped
`retention apply`, changes recorded (S5), surfaced in `doctor`. **CMP-4** graduate ed25519 checkpoint signing to a
documented default posture: key generation/rotation story, verification folded into `verify-store`/`evidence`/AAT
export, state in `/healthz`/`doctor`.

**Data & schema impact.** New command + templates + retention profiles; signing becomes a supported posture.

**Security & privacy.** Offline, air-gapped; no phone-home (R6); retention honors D-K (tombstone, never hard delete).

**Edge cases.** A report row with no evidence → fails, not omitted; a missed retention run degrades visibly; key lost
→ new epoch (bundles state which epoch signed them).

**Dependencies.** PRD 39 (W1/W2/W7/W9), PRD 41 (AAT), E1 checkpoints, S1 evidence, S5 recorder-state.

**Testing.** Zero unverifiable claims (executable-docs gate extended to report output); offline run; a tampered
signature fails; a missing key reports "signed by key id X, key unavailable."

**Risks & mitigations.** Report read as certification → explicit non-conformity statement (W1 discipline);
overclaiming origin → "this installation," not "this human."

**Decision.** D-44.x — retention vocabulary + signing default posture.

### SIEM-1..2. SIEM sink hardening + OCSF event stream · v0.2.0 · (new)

**Why.** SOC platforms are being rebuilt around agent telemetry (Microsoft ISOC, Exabeam ABA, Menlo→Google SecOps);
third-party ingestion is expensive, so lean schema-stable identity-attributed event streams are the adoptable
shape. Exabeam-class ABA cannot baseline an agent it cannot identify (needs IDN-1). We have OCSF mappings + opt-in
sinks (S10); they need hardening and documentation.

**Behavior.** **SIEM-1** conformance-tested OCSF 1.5.0 event stream with CI-exercised reference consumers per flavor
(Splunk/Sentinel/Exabeam-shaped). **SIEM-2** a Syslog sink alongside file/webhook. Per-sink redaction self-test gate
mandatory; backpressure → visible `degraded` (pairs with PRD 42 STR).

**Data & schema impact.** Events-only output (bounded; no raw records); no record change.

**Security & privacy.** Opt-in egress, S10 gating; identity + detector telemetry present per event but redacted.

**Edge cases.** Sink unreachable → bounded queue + `degraded`; over-limit event → truncated marker (S36).

**Dependencies.** S10, S8 (OCSF), PRD 43 (detector telemetry), IDN-1.

**Testing.** Reference consumers green in CI; redaction gate blocks an unconfigured sink; degraded surfaced on
failure.

**Risks & mitigations.** Becoming a SIEM → events only, no dashboards (PRD 14); ingestion cost → lean events.

**Decision.** D-44.y — sink flavor matrix + Syslog format.
