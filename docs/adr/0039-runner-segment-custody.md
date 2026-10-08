# ADR-0039 — Runner segment custody semantics

- **Status:** accepted (2026-10-07, v0.2.0 M30)
- **Context:** PRD 58 §RUN-1, [design/runner-segments.md](../design/runner-segments.md), issue #479.
- **Supersedes:** none.

## Context

Background/cloud/CI agents are where oversight is thinnest and where agentwatch has no daemon or home. Such a
run can still produce evidence if it seals its own segment and uploads it as a CI artifact. The open questions
are custody: what integrity does an imported segment have relative to a locally-recorded session, and can a
consumer ever mistake the two?

## Decision

1. **A segment carries its own chain and attestation, not the local store's.** The runner seals the run's
   records under its **own** genesis hash chain plus a runner identity and a start/end attestation. Verification
   (member sha256 + re-hashed chain from genesis + attestation present) is independent of any local store.
2. **Import is anchoring, not witnessing.** `import-segment` verifies the segment and appends a
   **chain-of-custody anchor record** (`runner-segment`, action `import`, runner identity, segment digest,
   custody statement, egress=false) followed by the records. Imported records are therefore **chain-protected
   locally** (they are in the local hash chain) but **never locally witnessed**.
3. **The distinction is explicit and permanent.** Imported records carry `producer.kind=import`,
   `producer.name=runner-segment`; `custody_rows` labels them `source: runner` / `locally_witnessed=false`,
   and `union`/`sessions`/`provenance` see them as non-hook provenance. A consumer can always tell an imported
   runner record from a locally-harnessed one.
4. **Zero egress, redacted only.** agentwatch performs no upload: the user moves the artifact. Sealing and
   import both refuse `privacy_mode=full` records. A tampered segment fails verification and is not imported.
5. **Trace correlation travels with the join.** When the segment carries a `traceparent`, import joins the
   runner session to the originating local session(s) by trace id and records the join (and the custody
   statement) on the anchor.

## Consequences

- An unattended run lands in the same store as harness records but can never masquerade as locally witnessed
  evidence; the weaker custody is visible at every surface.
- The segment is portable: it needs no agentwatch on the runner and no daemon/home.
- Cross-host custody is stated per import; there is no continuous chain between runner and host (a declared
  limitation).
