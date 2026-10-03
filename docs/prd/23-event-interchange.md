# PRD 23 — Ecosystem Event Interchange

**BLUF:** Publish and consume the plumbing: security-event ingestion, the store/socket contract, and session export for agentdrill.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### B2. Ecosystem event ingestion (`agentwatch event emit`) · M5 · #171

**Why (evidence).** CUJ-4's success criterion is "the schema is published and **≥1 other
ecosystem tool** emits it." There is currently no API/socket path for agentpolicy, agentkeys, or
agenthalt to deliver an event to the store — the R5 story is half-built. PRD 09 calls agentwatch
the dependency root; this is the dependency edge others need.

**Behavior.** A sibling tool (or operator) can emit a validated security event:
```sh
agentwatch event emit policy-fired --session-id $SID --tool Bash \
  --reason "rate limit" --evidence '{"policy_id":"p-1"}'
```
It lands in the same tamper-evident chain as records and appears in `sessions`/replay for its
session. Over the daemon socket, the message is
`{"phase":"event","harness":"<emitter>","event": <SecurityEvent>}`.

**Data & schema impact.** Reuses `validate_event` (M2, shipped) — reject-never-coerce (F8). The
store has no standalone-event form, so the daemon appends a **carrier record**:
`tool.name="external-event"`, `outcome=ok`, `security_event=<event>` (convention matches
`hook-error`; no schema change) — D-A.

**Security & privacy.** Socket is owner-only (0600); events are small metadata. An invalid event
is rejected with the offending field named and is **quarantined** (B4), never silently dropped.
Emitter provenance is preserved (`emitter` field) so an audit can tell agentwatch-native from
agentpolicy-emitted events.

**Edge cases.** Event for an unknown/absent session → create a synthetic session? (recommended:
attach to a session named by `--session-id`, else `"external"`). Duplicate event (same
`event_version:type:span_id:seq`) → dedup via F2 idempotency. Emitter omitted → default
`"agentwatch"`? (recommended: require `emitter`).

**Dependencies.** `validate_event` (shipped); daemon socket (shipped); B4 quarantine; J1
published protocol.

**Testing.** Round-trip: emitted `policy-fired` validates, chains, and shows under its session;
invalid event is rejected naming the field and quarantined; two sibling-style emitters produce
distinguishable provenance.

**Risks & mitigations.** Sibling tools on a different user account can't reach the 0600 socket
— document as a v0.1.0 limitation (multi-user is fleet, R13). Event spam — rate-limit/log.

**Decision.** D-19.7 (carrier-record convention), D-19.8 (require emitter?).


### J1. Publish the plumbing contract (store format + socket protocol) · M10 · #203

**Why (evidence).** Our equivalents of git's object model — the store envelope, the daemon socket
protocol, the adapter conformance suite — are what the ecosystem (agentpolicy, agentdrill,
agentcomply) and community harness adapters (R10) build on. Only the JSON schemas are published
today; the rest is an undocumented private API, and private APIs make poor ecosystems.

**Behavior.** Versioned, published specs for (a) the store envelope and chain, (b) the daemon
socket protocol (framing, phases, hook-error/event frames), and (c) the adapter contract
(capabilities, gaps, conformance). Each carries an explicit compatibility commitment (additive
minor, breaking major + deprecation).

**Data & schema impact.** New `docs/reference/store-format.md` and
`docs/reference/daemon-protocol.md`; the conformance suite becomes the plugin contract.

**Security & privacy.** Documents what is captured and how it is redacted; must state the trust
boundary. Publishing the socket contract is owner-only (0600); no secrets in the spec.

**Edge cases.** A community adapter built to an older spec → conformance reports the version
mismatch. Protocol additions must be additive (new phases) not renames.

**Dependencies.** Store/lock (M4); socket (M3); O1 conformance runner; N4 version matrix.

**Testing.** Docs link-check; a sample external adapter passes conformance against the published
contract.

**Risks & mitigations.** Freezing a protocol too early (mark v0.1.0 experimental; commit at
v1.0).

**Decision.** D-19.24 (when the protocol is declared stable).

### J2. Replay as code — session export for agentdrill · M13 · #204

**Why (evidence).** PRD 09 makes agentwatch the dependency root: agentdrill replays what
agentwatch records. That needs a stable, machine-consumable session export — which does not
exist; today records can only be looked at.

**Behavior.** `agentwatch export-session <id> --format ndjson` emits the session's records in
order, including its chain segment (seq/prev_hash/hash), designed for agentdrill and CI.

**Data & schema impact.** New exporter; output is the store envelope subset for one session,
schema-stable.

**Security & privacy.** Export inherits the store's redaction; no raw content beyond what is
stored. Warn that an export is evidence and should be handled as such.

**Edge cases.** Session with tombstones (retention) → export marks gaps, does not silently omit.
Broken chain → export refuses unless `--allow-broken`, and flags it. Cross-session (resumed)
sessions → include linked ids (I3).

**Dependencies.** Store (M4); I3; J1 contract.

**Testing.** Export round-trips through a reference consumer; tombstone/broken-chain behavior.

**Risks & mitigations.** Drift between export and agentdrill's expectations (contract + consumer
test in CI).

**Decision.** D-19.25 (export completeness vs size).

