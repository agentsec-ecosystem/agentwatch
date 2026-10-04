# PRD 37 — Configuration, Profiles & Capture Hygiene

**BLUF:** Make the recorder legible and safe to live with: explain the effective configuration (S34), install
with **named profiles** instead of a decision list (S35), bound the single pathological record (S36), expose
the SDK and hook producers behind one read surface (S11), and reuse the redactor as a standalone primitive
(S13).

**Status:** shipped (2026-10-03) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M21

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### S34. `agentwatch config explain` · v0.1.0 · (new)

**Why.** PRD 16 defines five precedence layers — system < user < project < env < CLI — with strict unknown-key
rejection. That is the right design and it produces the question the design invites: *why is this value what it
is?* When export is unexpectedly disabled or the store path is not where someone expects, there is no way to
see which layer won. The PRD cites the git-config lesson about surprising the user; this is the other half.

**Behavior.** `agentwatch config explain [KEY]` prints each key's effective value, the layer that set it, the
file and line, and the layers it overrode — with `--diff` showing only where the resolved config departs from
defaults.

**Data & schema impact.** Read-only over `configuration.py` (shipped); no record change.

**Security & privacy.** Must never print secret-bearing values (none should exist in config per PRD 18, so
this doubles as a check that none do).

**Edge cases.** A key set by no layer → default, labelled; an unknown key → error naming it; env override →
shadowed layers still listed.

**Dependencies.** `configuration.py` (shipped), S35, S5 (`config-changed` records).

**Testing.** A key set at three layers reports the winning layer and the overridden ones; `--diff` lists only
non-defaults; no secret value can appear.

**Risks & mitigations.** None material.

**Decision.** New — output shape and `--diff` semantics.

### S35. Install profiles · v0.1.0 · (new)

**Why.** PRD 16's configurability lands on the user as a decision list at the worst moment — during install,
before any intuition. The four real-world postures differ sharply: a solo developer wants maximum capture and
no ceremony; a team wants metadata-only and shared defaults; a compliance install wants full retention, chain
checkpoints, and evidence on; a CI install wants ephemeral, headless, no daemon supervision. Making users
assemble these from primitives guarantees most installs run defaults that fit nobody.

**Behavior.** `agentwatch init --profile solo|team|compliance|ci`, each a named, documented bundle of existing
settings, printed in full by the consent-first plan (G3) before anything is written, and recorded as a
`config-changed` record (S5) naming the profile.

**Data & schema impact.** Presets over existing config keys; no new semantics.

**Security & privacy.** Config presentation only; consent-first print before write.

**Edge cases.** An explicit `--set` alongside `--profile` → the `--set` wins (CLI precedence), reported by
S34. An unknown profile → error listing valid names.

**Dependencies.** PRD 16, G3 consent-first init, S5, S34.

**Testing.** Each profile validates; `init --profile compliance` prints the full bundle before writing and
records one `config-changed`; a profile + `--set` resolves correctly.

**Risks & mitigations.** Profile drift from the underlying keys → generate the profile docs from the
definitions and test each validates.

**Decision.** New — the four profiles' exact bundles.

### S36. Guard the single pathological record · v0.1.0 · (new)

**Why.** F3 caps the *store*; nothing caps a *record*. One 200 MB tool response, one million-element argument
array, or one deeply nested object can exhaust memory on read, blow the size cap in a single append, or produce
a JSONL line no consumer can process — and `store.py` reads the whole file into memory, so one bad line degrades
every command afterwards. I1 (capturing responses) makes this materially more likely, since responses are the
field the agent's environment controls directly and without bound.

**Behavior.** Per-record limits with honest truncation: maximum serialized record size, maximum argument/response
field size, maximum nesting depth, maximum line length. Exceeding a limit truncates with an explicit marker
(`truncated: {field, original_bytes, rule}`) rather than dropping the record or failing the append.

**Data & schema impact.** New truncation marker on the record; limits are config keys (generous defaults).

**Security & privacy.** Capture hygiene; nothing blocked.

**Edge cases.** A record over the total-size limit → truncated with the marker, still appended. Truncation must
be **visible in the record** — a silently shortened response is a lie about what the agent saw, worse than an
obvious gap. Pairs with S32's receipts.

**Dependencies.** I1, M4 store, S32.

**Testing.** An oversized response is truncated with a marker naming the field and original size; the record
still validates and appends; `--receipts` shows the truncation rule.

**Risks & mitigations.** Truncating something forensically important → limits configurable, defaults
generous, the marker records exactly what was lost.

**Decision.** New — default limits and the marker shape.

### S11. Close the P5 hole — read-time union of SDK spans and harness records · v0.1.0 · (new)

**Why.** P5 (the embedder) is a listed persona with **no CUJ**, and PRD 14 defers "SDK→local-store
unification" to v0.2.0 for a good reason (two producers on one hash chain needs ordering and identity design).
The side effect is that v0.1.0 ships two products in one repo: hook records in the local chain, SDK spans in
OTLP/Postgres, with no surface where a user sees both. For a project whose thesis is *unification* ("one
install, one record format, one event schema"), that is the most visible incoherence in the release.

**Behavior.** The cheap 80%: a **read-time** union, not a write-time one. The read API (M7) and UI expose both
sources behind one query with an explicit `source: hook | sdk` field; `sessions` and `search` can list SDK runs
as read-only entries. No shared chain, no ordering guarantees, no invariant changes.

**Data & schema impact.** Read-only composition; no invariant change. The deferred chain-unification decision
stays deferred.

**Security & privacy.** Read-only. Only hook records are chain-protected — the `source` field is mandatory in
output and the integrity distinction is stated at every surface.

**Edge cases.** A session id colliding across sources → namespaced by `source`; an SDK-only query → returns SDK
runs and states they are not chain-protected.

**Dependencies.** M7 read API, SDK (ported); v0.2.0 decision untouched.

**Testing.** A query returns both sources with `source` set; the UI labels SDK entries as not chain-protected.

**Risks & mitigations.** Users assuming SDK spans are tamper-evident → mandatory `source` + stated distinction.

**Decision.** New — whether P5 gets a v0.1.0 journey or is demoted in PRD 04 (open question in
`next-ideas.md`).

### S13. The redactor as a reusable, standalone primitive · v0.1.0 · (new)

**Why.** `agentwatch.secrets` is the most defensible asset in the repo: deterministic, corpus-tested, and the
foundation of the "0 leaks" claim. It is reachable only inside the write path. Exposing it as a library + filter
(`agentwatch redact < in > out`) lets agentpolicy, agentdrill, and agentcomply reuse *one* redaction
implementation instead of writing four — the ecosystem-unification thesis and the cheapest way to make
agentwatch structurally load-bearing.

**Behavior.** A documented public API (`redact(text, mode) -> (text, findings)`), a stdin/stdout filter with
`--mode`, and a stable findings schema (kind + location + never the value, matching G1's rule). S32's
`--preview` builds on this.

**Data & schema impact.** New public API surface + filter; findings schema published.

**Security & privacy.** Local, deterministic, no LLM, no egress.

**Edge cases.** Empty input → empty output, no findings; binary input → handled per the documented rules;
unknown mode → error, no silent default.

**Dependencies.** M4 secrets, G1, S32.

**Testing.** The filter masks the corpus the same way the write path does; findings never contain a value; the
public API is exercised by an out-of-tree-style test.

**Risks & mitigations.** Public API freezes an internal shape → mark experimental in v0.1.0, commit at v1.0
(the same policy J1 uses).

**Decision.** New — API shape and the experimental→stable commitment.
