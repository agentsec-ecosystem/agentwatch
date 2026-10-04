# PRD 32 — Coverage & Recorder Trust

**BLUF:** The recorder proves its **integrity** (`verify-store`) and its **privacy** (`verify-privacy`) but
not its **coverage**. This PRD answers "did you capture everything that happened?" by reconciling the store
against an independent ground truth, records the recorder's own state transitions in the chain, and treats
the recorder as an attack target with a published detection matrix.

**Status:** shipped (2026-10-03) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M16

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

The founding lesson — "distinguish a **clean run** from **couldn't read the run**" (#102, quoted in
`01-why.md`) — is asserted at runtime (NFR-12) and never measured after the fact. Every item here turns a
trust question into a command or a record.

### S2. `agentwatch coverage` — reconcile the store against ground truth · v0.1.0 · (new)

**Why.** The three trust questions have two answers: *intact?* → `verify-store`; *leak-free?* →
`verify-privacy`; *complete?* → **nothing** — and completeness is the one a security engineer doubts, because
the failure modes are documented: workspace-trust gating suppresses project hooks in headless `-p` runs (G4),
daemon outages create gaps (F1/B3), undecodable events are quarantined (B4), transcript formats drift (H1).
Each is handled individually and honestly; no command sums them into a number.

**Behavior.**
```sh
agentwatch coverage [--since 7d] [--project PATH] [--session ID] [--json]
```
Per project/session: `tool calls in transcript` vs `records in store`, a capture rate, and every discrepancy
**classified by cause** — `gap:daemon-down`, `gap:quarantined`, `gap:trust-gated-headless`,
`gap:hook-not-installed`, `gap:transcript-format-drift`, `gap:harness-drift` (S19), `gap:unexplained`.
`gap:unexplained` should be zero; when it is not, that is a bug report with a reproduction.

**Data & schema impact.** Reads existing records + B3 gap events + B4 quarantine + hook-error records +
S5 coverage windows. No new record type (may emit an S5 coverage-window pair per run).

**Security & privacy.** Read-only; reads raw transcripts under the **A5 allow-list discipline** (counts and
tool names only, never content) — reuse A5's extractor verbatim, with the same canary test.

**Edge cases.** No transcripts present → coverage is "unknown for period," never 100%. A session with a gap →
partial rate with the cause. Clock skew (B5) → window boundaries reported, not silently trimmed.

**Dependencies.** H1 importer internals, B3/B4, G4 preflight reasons, hook-error records, S5.

**Testing.** A seeded gap of each class is classified with the right cause; `gap:unexplained` stays zero on
a clean fixture; the canary test proves no transcript content is read.

**Risks & mitigations.** Re-reading raw transcripts widens the most sensitive read path → single shared
extractor + mandatory canary test.

**Decision.** D-31.1 — accept the second A5 read path (see open question in `next-ideas.md`).

### S5. Recorder-state audit records — close the "quietly turned off" hole · v0.1.0 · (new)

**Why.** The chain proves stored records were not altered; it says nothing about **changing what gets
recorded**. `init`, `uninstall`, a privacy-mode downgrade, a retention change, or an export reconfiguration
leave no trace. A deliberate `uninstall` at 14:02 then `init` at 15:30 is invisible — indistinguishable from
an idle laptop. `session-purge` (shipped) already establishes the right precedent: a metadata-only marker,
never a silent change.

**Behavior.** Chain records for recorder-state transitions: `recorder-installed`, `recorder-uninstalled`,
`config-changed` (key + old/new value, metadata only, secrets excluded), `privacy-mode-changed`,
`retention-changed`, `export-configured`, `coverage-window-open`/`coverage-window-close`. `verify-store`,
`coverage` (S2), and the evidence bundle (S1) read them, so a bundle can state **"recording was active from
T1 to T2, configured as X."**

**Data & schema impact.** Reuses the marker-record convention; new marker tool names. No record-schema
change.

**Security & privacy.** Metadata-only; no new read paths; no egress. Config values are never secrets
(PRD 18 requires none in config).

**Edge cases.** Rapid identical transitions → coalesced. Missing config before a change → `old: unknown`.
A crash leaves no `coverage-window-close` → S2 treats the window as open-ended, not complete.

**Dependencies.** Store (M4), purge-marker convention (shipped), PRD 16 config loader.

**Testing.** `init`/`uninstall`/privacy downgrade each append one marker; `coverage` reads the window; no
secret value appears in a `config-changed` record.

**Risks & mitigations.** Config churn noise → coalesce rapid identical transitions; never record secret
values.

**Decision.** D-31.2 — marker naming and `coverage-window` semantics.

### S19. Harness-drift canary from real traffic · v0.1.0 · (new)

**Why.** N4 tracks harness versions from release metadata and G4 preflights at install; both learn about a
change *after* it is published. The failure mode that matters is silent: the harness renames a field, adds a
hook phase, or changes a payload, and agentwatch keeps exiting 0 while recording less. The adapter sees the
truth on every event and currently discards it.

**Behavior.** The adapter counts unrecognized top-level fields and unknown hook phases it is handed —
**names only, never values** — and records a periodic, debounced `harness-drift` observation with the unknown
keys and harness version. `doctor` and `/healthz` surface it; `coverage` (S2) cites it as a gap cause.

**Data & schema impact.** Reuses the metadata-only observation convention; feeds S2 classification and N4.

**Security & privacy.** Metadata only, local, no egress; observation, not enforcement. Field *names* from an
untrusted payload are themselves untrusted → allow-list characters, cap length/cardinality, never echo a value.

**Edge cases.** Additive fields are normal → framed as "additive" not "broken"; a new hook phase → reported
by name only; a high-cardinality field name → capped.

**Dependencies.** M3 adapter, B1 health, S2, N4.

**Testing.** A fixture with an unknown top-level field emits one debounced observation naming the field and
no value; a repeat within the session does not duplicate.

**Risks & mitigations.** Noise on additive-change harnesses → debounce + documented "additive is normal."

**Decision.** D-31.3 — debounce window and observation cadence.

### S27. Operator tooling for the quarantine · v0.1.0 · (new)

**Why.** B4 quarantines undecodable events so nothing is silently dropped — then leaves a dead-letter queue
with **no operator commands**: nothing lists it, explains why an entry landed, reprocesses it after a fix, or
clears it. `verify-privacy` special-cases it precisely because it may hold raw, unredacted content. An
append-only pile of raw payloads with no tooling is the one place the honest choice created a new hazard.

**Behavior.** `agentwatch quarantine list | inspect <id> | requeue [--all] | clear --yes`. `list` shows
reason + arrival time, no payload; `inspect` prints the payload **redacted by default** (`--raw` requires
explicit confirmation); `requeue` re-runs entries through the current adapter; `clear` is explicit and
reported.

**Data & schema impact.** New operator commands over B4's existing quarantine file; no record change.

**Security & privacy.** Local, owner-only, explicit consent for raw access; a raw inspect is recorded as a
`store-access` record (S21).

**Edge cases.** Requeue of an entry that still fails → stays quarantined with the new reason. `--raw` on a
missing id → error, no partial output. `clear` with entries → requires `--yes`.

**Dependencies.** B4 (shipped), M4 secrets, S21.

**Testing.** Requeue after a fix moves an entry into the store; `inspect` redacts by default; `--raw` is
recorded; `clear` without `--yes` is refused.

**Risks & mitigations.** `inspect --raw` becomes the leak the posture prevents → redacted default, gated raw,
access recorded.

**Decision.** D-31.4 — requeue semantics (adapter selection) and `--raw` confirmation shape.

### S30. Treat the recorder as an attack target · v0.1.0 · (new)

**Why.** agentwatch observes an agent that runs on the same machine, as the same user, with shell access. An
agent — or anything that compromised one — can stop the daemon, truncate the store, rewrite
`.claude/settings.local.json` to remove hooks, fill the disk to trip F3, or race the socket. PRD 06 names the
tamper scenarios and PRD 28 hardens file posture; what is missing is the **adversarial test suite** that tries
them and the published statement of what an on-box attacker can and cannot do.

**Behavior.** An anti-forensics suite (test + docs, not enforcement) covering: kill the daemon mid-session;
truncate/append-garbage to the store; strip hooks from settings; exhaust disk; hold the socket; move the
store; skew the clock; replay stale frames. For each, assert the documented outcome — detected, surfaced, and
*which* command reveals it — then publish a matrix: *detectable after the fact* vs *preventable* vs *neither*.

**Data & schema impact.** Tests + a docs matrix; no new capture, no enforcement.

**Security & privacy.** Deliberately not agentdrill: no attack packs against the agent, no evals — the
recorder's own fault-injection suite, extending F1–F10 from "things that break" to "things broken on purpose."

**Edge cases.** A scenario with no detection → listed as "neither" with the compensating control (S2/S5).
A detection that requires a manual command → named explicitly.

**Dependencies.** PRD 06 threat model, F1–F10 suite, S2, S5.

**Testing.** Each anti-forensics scenario has a test asserting the documented detection (or the documented
absence of one).

**Risks & mitigations.** Publishing an evasion matrix as a how-to → framed as threat-model test evidence;
every "not preventable" row paired with the detection that covers it.

**Decision.** D-31.5 — the matrix's three columns and which command evidences each row.

### S28. Seal and archive old segments · v0.1.0 · (new)

**Why.** NFR-3 promises bounded storage growth and R11 delivers retention — but retention *tombstones*, which
by design keeps every line so the chain still verifies. The file therefore never shrinks; a year-old store is
mostly tombstones and still grows monotonically, and F3's size cap responds by refusing to record. Bounded
growth and a verifiable append-only chain are in direct tension, and nothing resolves it.

**Behavior.** `agentwatch archive --before DATE [--out DIR]` moves a prefix of the chain into a sealed segment
file, leaves a single **anchor record** in the live store (segment id, record range, segment hash, count), and
keeps the archive independently verifiable with the same verifier (S12). `verify`, `search`, and `replay` read
archives when present and say plainly when they are absent.

**Data & schema impact.** New anchor record + segment file format; reuses the store envelope and chain rules.

**Security & privacy.** Local, verifiable, lossless; the operator chooses the destination.

**Edge cases.** A missing archive → every read that crosses an archived range reports the archive as
present-but-unavailable, never as empty. An archive whose hash disagrees with the anchor → surfaced as a break.
Un-archiving (restore) → the anchor is consumed and the range reintroduced, with the operation recorded.

**Dependencies.** E1 checkpoints, S12, Q6 vectors.

**Testing.** Archive then verify the segment independently; the anchor preserves the range; a moved-away
archive is reported unavailable; `replay` across the boundary reads both.

**Risks & mitigations.** A missing archive silently narrowing results → always report present-but-unavailable,
never empty.

**Decision.** New — segment file format and anchor-record shape.
