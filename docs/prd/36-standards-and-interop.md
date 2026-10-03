# PRD 36 — Standards & Ecosystem Interop

**BLUF:** Make agentwatch a good ecosystem citizen: emit security events in **OCSF** and **CloudEvents**,
publish a **reference consumer**, ship an **OTel Collector component**, provide opt-in **event forwarding
sinks**, and prove the schema's first new event type (**MCP tool-surface drift**) through proper stewardship.

**Status:** proposed (2026-10-03) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, **no egress without explicit opt-in** (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

The distinction running through this PRD: **emitting a standard is export, not becoming the standard's
consumer.** Agentwatch is not a SIEM (PRD 14) — but emitting an OCSF mapping is exactly as much "being a SIEM"
as emitting OTLP makes it a tracing backend. Every item here is opt-in, open-format, and local-first.

### S8. OCSF + CloudEvents mappings for the security-event schema · v0.1.0 · (new)

**Why.** R5's success criterion is *adoption* — the schema is published and emitted by ≥1 other tool, with a
12-month stretch goal of a non-ecosystem adopter (PRD 07). Adoption by security teams is gated on one question:
*does it land in my SIEM?* OCSF is the open, vendor-neutral security-event standard (Splunk/AWS/Cloudflare/
CrowdStrike et al. consume it); CloudEvents is the open envelope for the `event emit` path (B2). Shipping both
mappings costs a transcode and a doc and moves agentwatch from "a schema someone invented" to "a schema that
speaks the two standards the receiving side already speaks."

**Behavior.** A published mapping table (agentwatch event type → OCSF class/category/activity, unmapped fields
in `unmapped`), `agentwatch export --format ocsf`, and an optional CloudEvents envelope on B2's socket/CLI
event path. Round-trip and conformance tests against the OCSF schema validator in CI.

**Data & schema impact.** New export format + mapping doc; agentwatch's schema stays the source of truth.

**Security & privacy.** Export only, opt-in, open standards, no ingestion, no hosted anything.

**Edge cases.** Fields OCSF cannot express → `unmapped`, documented (lossless-or-explicit); a new event type
without a mapping → exported with an explicit `unmapped` marker, never dropped.

**Dependencies.** R5 schema (shipped), export plumbing (M5), W3.

**Testing.** Every shipped event type maps to a documented OCSF target or an explicit `unmapped`; the OCSF
output validates against the pinned schema version; the CloudEvents envelope validates.

**Risks & mitigations.** Mapping drift as OCSF versions → pin the OCSF version in output and test against it.

**Decision.** New — explicit record that emitting a mapping is export, not SIEM ingestion (open question in
`next-ideas.md`).

### S38. A reference consumer, not just a contract · v0.1.0 · (new)

**Why.** R5's adoption goal is won with **working code someone can copy**, not a specification. J1 publishes
the store format and socket protocol; O1 gives adapter authors a conformance runner. Nothing shows the other
side: how a sibling tool subscribes to events, validates them, and reacts. Every ecosystem project will write
that integration, and without a reference each invents a different one, fragmenting the convention at exactly
the layer it was meant to unify.

**Behavior.** A small, complete, tested example consumer in `examples/` — subscribes to security events,
validates against the published schema, prints or forwards them — ~100 lines, run in CI against a fixture
stream so it cannot rot. The mirror of the community-adapter example on the producer side.

**Data & schema impact.** Example code; no new runtime surface.

**Security & privacy.** Example code, local; labelled a reference, versioned with the schema.

**Edge cases.** Schema drift breaks the example → CI catches it. No daemon reachable → example states it.

**Dependencies.** B2, J1, S10, W5.

**Testing.** The example runs in CI against a fixture event stream and validates each event.

**Risks & mitigations.** Mistaken for a supported product → labelled a reference, versioned with the schema.

**Decision.** New — sample language/scope and where it lives.

### S39. An OTel Collector component · v0.1.0 · (new)

**Why.** R4's claim is that records load into standard backends unmodified, and the honest current answer is
"after you configure a collector correctly." The last mile — a packaged receiver/processor that reads the
agentwatch store or socket and emits GenAI-semconv spans — turns the claim into a drop-in. It is also the
highest-leverage distribution channel: the collector registry is where platform engineers already look, and
arriving there as a component reaches Maya (P1) without her ever hearing of agentwatch.

**Behavior.** A collector receiver (and a mapping processor) built from the existing export code, distributed
through the normal collector-component path, with a conformance test asserting emitted spans match the pinned
semconv version (W4).

**Data & schema impact.** New distributable built on M5 export; no record change.

**Security & privacy.** Export path only, opt-in, open standard.

**Edge cases.** Semconv version drift → the component pins and reports the version (W4). Missing store →
receiver reports unavailable, does not fabricate spans.

**Dependencies.** M5 export, W4 semconv pinning, S8.

**Testing.** The component's output validates against the pinned semconv; a fixture store produces the expected
spans.

**Risks & mitigations.** Maintaining a component against collector API churn → keep the mapping in agentwatch
and the component thin.

**Decision.** New — receiver vs processor split and distribution packaging.

### S10. Security-event forwarding sink (file / webhook / syslog), opt-in, rule-free · v0.1.0 · (new)

**Why.** R5 adoption needs a path *out* that is not "stand up an OTLP collector." Consumers — agentpolicy, a
team Slack bridge someone writes in 20 lines, an auditor's file drop — need events delivered. #66's Slack-alerts
idea was correctly deferred as *alerting*, but **forwarding without rules is not alerting**, the same way
`tail --alert` (H5) is observation. Today a consumer's only options are to poll the store or read the 0600
socket; the `event emit` ingress (B2) was built with no egress peer.

**Behavior.** Config-declared sinks for **security events only** (never full records):
`file:///path/events.ndjson`, `https://…` (webhook, with retry + bounded queue + no payload beyond the event),
`syslog`. Off by default; `init` discloses it (G3); every delivery failure is a visible `degraded` state,
never a silent drop.

**Data & schema impact.** New opt-in sink config; no record change.

**Security & privacy.** Opt-in egress with explicit config — the same gate as OTLP export (R6/DD-09); the
redaction self-test gates it identically. No rules, no thresholds, no routing logic.

**Edge cases.** Webhook down → bounded queue + `degraded`, never an unbounded retry; a payload larger than the
sink accepts → event chunked or rejected explicitly, never truncated silently.

**Dependencies.** B2, DD-09 export gating, B1 health.

**Testing.** A configured file sink receives events; a webhook failure surfaces `degraded`; no record is ever
forwarded (events only); the self-test gates enabling a sink.

**Risks & mitigations.** Accreting into an alerting product → hard rule: sinks have **no filtering beyond
event type**, plus a decision record saying so.

**Decision.** New — sink config shape and the no-filtering rule.

### S4. MCP tool-surface snapshot + drift · v0.1.0 · (new)

**Why.** PRD 01 cites rug-pulls as a named, unmitigated, *unprovable-after-the-fact* threat. A rug-pull is
detectable with nothing but a record: **the tool surface a server presented changed between sessions.**
agentwatch already attributes `mcp__<server>__<tool>` into `tool.server`/`tool.name` (shipped, M9) — it has the
raw material and throws away the time dimension. This closes a promise the PRD makes about itself and gives the
rest of the ecosystem (agentpolicy, agentcomply) a primitive to consume.

**Behavior.** Per session, record one `mcp-surface` carrier record: server name, the set of tool names observed
(or enumerated, if the MCP interposition adapter N1 lands), and a digest of that set. Then:
```sh
agentwatch inventory --snapshot                 # current surface per server
agentwatch inventory --diff --server <name>     # surface changes over time, first/last seen
```
A change emits a **new security event type** — `tool-surface-changed` — carrying
`evidence={"server":…, "added":[…], "removed":[…], "prev_digest":…, "digest":…}`.

**Data & schema impact.** New event type (the first since R5's original five) → schema minor bump through W5's
published stewardship process; new `mcp-surface` carrier; additive.

**Security & privacy.** Recording + a named event; no blocking, no trust scoring. Metadata only.

**Edge cases.** Observed-surface (from usage) under-reports vs enumerated-surface (from `tools/list`) → the two
must be **distinct fields, not merged**; with N1 absent, say "observed" plainly. A first-seen server → no
`prev_digest`, so no change event.

**Dependencies.** D1 attribution (shipped), N1 (optional, improves fidelity), W5 (stewardship), schema version
bump.

**Testing.** A server whose tool set changes between two sessions emits one `tool-surface-changed` with
added/removed and both digests; an unchanged server emits none; observed vs enumerated are separate fields.

**Risks & mitigations.** Read as a malware verdict on the server → observation-only wording ("surface changed");
schema stewardship done properly rather than bolted on (W5).

**Decision.** New — whether the sixth event type lands in v0.1.0 and only after W5's process is published
(open question in `next-ideas.md`).
