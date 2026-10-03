# PRD 31 — Evidence & Provenance

**BLUF:** Turn records into **artifacts a third party can trust off-machine**: a self-contained,
offline-verifiable evidence bundle, a standalone verifier, an Agent Bill of Materials, an operator
annotation/audit trail, and a schema-level `producer` provenance field.

**Status:** proposed (2026-10-03) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification
> (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6);
> no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply
> (NFR-11).

The recurring gap this PRD closes: agentwatch *is* the evidence pipeline (PRD 18) yet **packages nothing**.
`export-session` (J2, #204) targets a machine consumer (agentdrill); a human auditor, customer, or regulator
needs a different artifact. Every item here is derived from data already stored; none adds a capture path,
enforcement, or egress.

### S1. `agentwatch evidence` — the self-contained, offline-verifiable incident bundle · v0.1.0 · (new)

**Why.** The postmortem owner (P2 Ravi) hands an artifact to legal, an auditor, or a customer, and it must
survive leaving the machine where it was produced. PRD 18 claims agentwatch "*is* the evidence pipeline" and
PRD 21 builds checkpoints/repair so evidence survives — then nothing packages it. The "evidence bundle" is
already scheduled at M13 in `additions-sequencing.md` with **no PRD section and no issue** — the most
compliance-valuable artifact is the least specified.

**Behavior.**
```sh
agentwatch evidence <session-id> [--out bundle.zip] [--include-bom] [--redact-paths]
agentwatch evidence verify bundle.zip        # re-verify, offline, no store needed
```
Bundle members: `manifest.json` (bundle format version, created-at, tool version, store format version,
schema `$id`s, sha256 of every member); `records.ndjson` (session records with full store envelope);
`chain.json` (chain segment + nearest checkpoints either side); `verify.json`/`verify.txt` (scoped
`verify-store` verdict: intact / gaps / tombstones / purges, enumerated); `privacy.json` (the
`verify-privacy` verdict under the config active at bundle time); `coverage.json` (the S2 verdict);
`inventory.json`/`bom.cdx.json` (S9); `summary.md` (deterministic narrative); `SCHEMA/` (exact schema
versions, so the bundle is self-describing forever).

**Data & schema impact.** New bundle format (versioned, open); reuses the store envelope and existing
verdict shapes. No change to record schema.

**Security & privacy.** Read-only, local, open formats, no egress (the operator moves the file). A bundle
contains redacted-but-sensitive paths/args → `--redact-paths` and a printed handling warning (J2 wording).

**Edge cases.** Session with tombstone/purge gaps → the bundle is still valid and says so on the front
page. Missing checkpoints → `chain.json` states anchors unavailable. A resumed session → include linked ids
(I3). Broken chain → bundle carries the verdict, never implies intactness.

**Dependencies.** Store/chain (M4), E1 checkpoints, E2 repair, G1 verify-privacy, I3, J2.

**Testing.** Bundle → `evidence verify` round-trip offline; the three verdicts (intact / complete /
leak-free) are reported independently, never collapsed; a tampered member fails verification.

**Risks & mitigations.** Treated as proof beyond what it shows → W6 forensic-soundness statement in the
bundle and docs.

**Decision.** New — bundle format version & compatibility commitment; whether `verify` is standalone (S12).

### S12. A standalone, dependency-free bundle verifier · v0.1.0 · (new)

**Why.** A bundle only verifiable by installing the tool that produced it is weak evidence. Auditors and
incident responders on someone else's laptop need to verify a chain segment with no Python env, daemon, or
network.

**Behavior.** `agentwatch-verify` as a stdlib-only zipapp plus a published ~100-line reference
implementation in the docs, both run against the conformance vectors (Q6) in CI.

**Data & schema impact.** No new schema; consumes the S1 bundle and J1 published store format.

**Security & privacy.** Read-only, no deps, no network.

**Edge cases.** Third-party reimplementation disagrees → vectors fail; a bundle using an unknown format
version is rejected with the version named.

**Dependencies.** S1, J1, Q6.

**Testing.** Both the shipped verifier and the doc reference implementation pass the same vectors;
tampered vectors fail both.

**Risks & mitigations.** A second implementation drifting from `store.py` → both run against the same
vectors in CI; drift is a test failure.

**Decision.** New — distributable form (zipapp) and versioning of the verifier itself.

### S9. `agentwatch bom` — an Agent Bill of Materials per session (CycloneDX) · v0.1.0 · (new)

**Why.** Supply-chain questions about agents are asked now and unanswered: *which models, MCP servers, tool
surface, and prompt/ruleset version did this agent have?* agentwatch captures every component already
(`inventory`, `agent.model_version`, `prompt_version`, `tool.server`) and emits them as separate views.
Rendered as CycloneDX (ECMA standard with ML-BOM/SaaSBOM component types) it becomes an artifact
procurement, security review, and compliance already consume.

**Behavior.**
```sh
agentwatch bom [--session-id ID | --project PATH | --machine] --format cyclonedx|json
```
Components: models (name+version), MCP servers (name + observed/enumerated tool-surface digest, S4),
prompt/ruleset digests, harness+version (N4), agentwatch itself. Mandatory `coverage` field stating the BOM
is *observed*, over which window, and what it does not claim.

**Data & schema impact.** New export format; consumes D1/D2, A5, S4, N4. No record change.

**Security & privacy.** Derived read, open standard, local.

**Edge cases.** Sessions with no models/tools observed → components omitted with an explicit "none
observed"; a mixed-project BOM → per-project scope stated.

**Dependencies.** D1/D2 (shipped), A5, S4, N4.

**Testing.** Generated BOM validates against the CycloneDX schema; the `coverage` field is present; an
unknown model is included by name without a fabricated version.

**Risks & mitigations.** Overclaiming completeness of an *observed* BOM → mandatory `coverage`; docs say
"observed during recorded sessions," never "installed on this machine."

**Decision.** New — CycloneDX schema version pinned in output.

### S26. A `producer` field on every record · v0.1.0 · (new)

**Why.** By v0.1.0 the store holds records from ≥5 sources — Claude Code hook, transcript import (H1),
`event emit` (B2), OTel ingestion (N2), MCP interposition (N1) — distinguished only by a convention
(`harness` + ad-hoc `evidence={"imported": true}`). Imported history is weaker evidence than live capture;
externally emitted events differ in provenance; S2's coverage math is wrong if it counts imported records as
captured. Provenance should be a schema field, not an inference.

**Behavior.** `producer: {kind: hook|import|event|ingest|proxy|sdk, name, version}` — required, validated.
`search --producer`; S1/S2 report per-producer counts.

**Data & schema impact.** Additive required field on the record schema (minor bump); older records default
to `kind: hook` on read, with the store format version recording that the value was inferred (Q7).

**Security & privacy.** Schema honesty; no new capture.

**Edge cases.** Unknown producer kind → rejected (F8). A legacy store → inferred `hook` on read, never
written back silently.

**Dependencies.** M2 records, W5 (stewardship), Q7.

**Testing.** Round-trip with the field; legacy fixture reads as inferred `hook`; an unknown kind is
rejected.

**Risks & mitigations.** Breaking existing stores → backward-compatible read default + format-version note.

**Decision.** New — field shape and minor-bump timing (rehearses W5 before S4/S14).

### S21. Log reads of the store, not just writes · v0.1.0 · (new)

**Why.** The store is forensic evidence (SOC 2 CC6/CC7), but every control is about *writing* integrity.
Nothing records **access**: who exported, who bundled, who surfaced a session with a `secret-detected`
event, where a bundle went. That is the half auditors ask about, because a record-keeping product
concentrates sensitive history in one readable file.

**Behavior.** Append metadata-only `store-access` records for operations that move data off-machine or into
a portable artifact — `export`, `export-session`, `evidence`, `bom` — with timestamp, command, scope
(session ids, record count), and destination kind (never credentials). Local read-only `search`/`view`/
`replay` are out of scope.

**Data & schema impact.** Reuses the metadata-only marker-record convention (`session-purge`, shipped).
No new schema field.

**Security & privacy.** Local, metadata only; records an action already taken, never gates it.

**Edge cases.** A failed export → recorded as attempted with the error; concurrent access commands →
records serialize through the store lock.

**Dependencies.** S1, J2, S5, M5 export.

**Testing.** `evidence`/`export-session` append exactly one `store-access` record with the scope; `search`
appends none; `verify-store` stays green.

**Risks & mitigations.** Scope creep into logging all reads → the four-command allow-list is the decision,
written down.

**Decision.** New — the allow-list boundary ("data left, or could leave").

### S20. `agentwatch annotate` — operator notes in the chain · v0.1.0 · (new)

**Why.** An investigation produces a conclusion that lives in Slack; the store holds machine evidence and
no human judgment, so the next reader repeats the work and an evidence bundle carries records without the
analyst's finding. The purge-marker convention already established operator-authored, metadata-only records
in the chain.

**Behavior.** `agentwatch annotate <session-id> --note "…" [--tag reviewed]` writes a metadata-only
`operator-note` record; `sessions --tag` filters by it; S1 bundles include notes as a `findings` section.

**Data & schema impact.** Reuses the marker-record convention; notes are append-only (added, never edited),
so corrections are new records.

**Security & privacy.** Local, metadata only. Free text is untrusted on render → cap length and run it
through the redactor (S13) before storing.

**Edge cases.** Empty note → rejected; a note containing a secret → masked before storage; a note on a
purged session → attached to the purge marker's session with an explicit "session purged" context.

**Dependencies.** Purge-marker convention (shipped), S1, S13.

**Testing.** Note round-trips as a record; `sessions --tag` filters; a secret in a note is masked.

**Risks & mitigations.** Injection into later views → untrusted-render discipline + redaction + length cap.

**Decision.** New — tag vocabulary (free-form vs enumerated).

### S32. Redaction receipts — show the user what was dropped · v0.1.0 · (new)

**Why.** Privacy-by-default asks users to trust a transformation they never see. `verify-privacy` proves
*no secrets survived*; nothing shows what the redactor *did* (fields masked, rule responsible, fields kept).
The cautious user cannot confirm their argument was handled; the over-trusting user never notices redaction
removed the field an investigation needed.

**Behavior.** `agentwatch replay <id> --receipts` / a `receipt` block on `--json`: per record, fields kept,
fields dropped, and the rule id (`secrets:aws-key`, `privacy-mode:metadata-only`, `truncation:4096`). Plus
`agentwatch redact --preview <sample>` running a user's own sample through the active config, before/after,
**storing nothing**.

**Data & schema impact.** Derived at read time; nothing added to the store.

**Security & privacy.** Names rules and field paths, never values (G1's rule). `--preview` never writes.

**Edge cases.** No masking on a record → empty receipt. A field dropped by both mode and secret rule →
both rules listed. Non-string fields → path only.

**Dependencies.** M4 secrets/redact, S13, S36.

**Testing.** A record with a masked secret and a dropped argument has both rules in its receipt; `--preview`
leaves the store byte-identical.

**Risks & mitigations.** A receipt naming a dropped field too specifically → field paths only; the rule id
carries the explanation.

**Decision.** New — receipt field paths vs whole-field granularity.
