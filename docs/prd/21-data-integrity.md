# PRD 21 — Data Integrity & Delivery Guarantees

**BLUF:** Never lose an event: spooling, exactly-once, gap records, quarantine, export cursor, store format versioning, checkpoints, repair, and least privilege.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### B3. Record recording gaps as events (F1) · M5 · #172

**Why (evidence).** PRD 17's headline guarantee: "a recording gap is always an event, never an
absence… operators can see 'recording stopped here and resumed here'." F1's recovery is "the gap
is recorded as a session-boundary event." Today a crash/restart leaves silence; an auditor cannot
distinguish a quiet hour from a dead recorder.

**Behavior.** On daemon start, if a previous daemon *was* running (evidence: the `daemon.pid`
from `install.py`) and the store's last record predates a threshold, the daemon synthesizes a
`recording-gap` record spanning the outage. It is chained between the old and new records.

**Data & schema impact.** `tool.name="recording-gap"`, `outcome=error`,
`started_at=last-record-time`, `ended_at=now`, `duration_ms=gap`, attributed to the open session
(with A1) or `"unknown"`.

**Security & privacy.** No content; a time gap only.

**Edge cases.** First-ever start (no pid, no records) → no gap. Clean stop (pid removed by
`uninstall`/SIGTERM) → no gap. Clock moved backward/forward → combine with F9 (B5); cap the
reported gap and flag skew. Daemon killed before writing pid → fall back to "store idle longer
than threshold" heuristic with a `reason`.

**Dependencies.** `install.py` pid file (shipped); A1 for session attribution; F9.

**Testing.** Fault test: start → record → SIGKILL → restart → gap chained; clean stop → no gap;
`verify()` green across the gap.

**Risks & mitigations.** False gaps on slow starts (threshold configurable; require pid
evidence first).

**Decision.** None new.

### B4. Quarantine undecodable events (F8) · M5 · #173

**Why (evidence).** F8: "the raw event is **quarantined** … kept for diagnosis, not hidden …
fix adapter; **reprocess** quarantined events." Today `handle_message` synthesizes a `hook-error`
record but **discards** the raw payload, so diagnosis and reprocessing are impossible — the
product throws away the very bytes needed to fix a parser.

**Behavior.** On a normalization failure, the raw frame is appended verbatim to
`<store.path>/quarantine.jsonl` (same hash-chained envelope, owner-only perms) and referenced
from the synthesized record. A future `agentwatch reprocess` replays the quarantine through the
fixed adapter.

**Data & schema impact.** Quarantine uses the store's envelope (chain integrity applies to
evidence too). The hook-error record gains `evidence={"quarantined": true, "line": N}`.

**Security & privacy.** The raw frame may contain secrets — it is stored **unredacted** because
quarantine is diagnosis evidence. This is a deliberate, documented tradeoff: quarantine is
owner-only (0600), excluded from export, and flagged. D-19.9: alternative is to store the frame
after best-effort secret masking (loses fidelity). Recommended: store raw, never export,
never include in `/healthz`.

**Edge cases.** Quarantine file grows → cap + rotate like logs (F6). Concurrent appends → same
lock as the store. Corrupt quarantine line → surfaced by a quarantine-specific verify.
Reprocess idempotency → keyed by (source line hash).

**Dependencies.** Store envelope/lock (shipped); F8; B1 health (quarantine size).

**Testing.** Malformed frame → hook-error + quarantine line containing original bytes; quarantine
excluded from `records()` and from export; quarantine verify green.

**Risks & mitigations.** Raw-secret retention in quarantine (owner-only + no-export + docs +
`verify-privacy` scans quarantine too — resolve in G1).

**Decision.** D-19.9 (raw vs masked quarantine).

### B5. Detect clock skew (F9) · M13 (M12 workload) · #174

**Why (evidence).** F9: "monotonic clock + UTC wall clock check … wall-clock skew is logged."
Timestamps underpin replay, retention cutoffs, and gap math; a wrong clock silently corrupts all
three.

**Behavior.** An event whose `timestamp` exceeds `now + skew_tolerance` (config, default 5 min)
is logged and stamped `evidence={"clock_skew": <seconds>}`; durations never use wall clock (they
come from the harness or are absent).

**Data & schema impact.** Uses `security_event.evidence` (no new field) or a `reason` on a
synthetic note. Config key added to PRD 16.

**Security & privacy.** None (timestamps only).

**Edge cases.** Small skew (< tolerance) ignored; large future skew flagged; large *past* skew
(clock moved back) flagged symmetrically; skew interacting with retention (never purge a
future-dated record — already guaranteed by M4 retention's `started_at < cutoff` check).

**Dependencies.** handle_message; PRD 16 config.

**Testing.** Injected future timestamp; injected past timestamp; retention keeps future records
(cross-check with M4 test).

**Risks & mitigations.** False positives on NTP step (log-only, never drop).

**Decision.** D-19.10 (tolerance default/configurable).

### E1. Chain checkpoints · M13 (M12 workload) · #179

**Why (evidence).** A single hash chain proves integrity but offers no *segmentation*: an auditor
cannot assert "by Tuesday 10:00 these N records existed" without scanning the file, and there is
no natural anchor point for evidence stored off-machine.

**Behavior.** Every N entries (config, default 1000) the store appends a checkpoint envelope
`{"seq", "prev_hash", "hash", "checkpoint": true, "entries": N, "at": <ts>}` — a normal link,
verified by the existing `verify()`.

**Data & schema impact.** New envelope variant `checkpoint`; `verify()` counts checkpoints in
`checked`; no record-schema change.

**Security & privacy.** Honest caveat, documented: a local attacker with write access can rewrite
checkpoints too; the value is segmentation plus the ability to export checkpoint hashes to an
external anchor (log, another host). PRD 18's "don't claim what you can't prove" governs the
wording.

**Edge cases.** Checkpoint exactly at a retention boundary; checkpoint after a repair (E2) —
re-anchor; gaps (B3) crossing a checkpoint.

**Dependencies.** Store (M4); E2.

**Testing.** `verify()` green across checkpoints; tamper between checkpoints detected at the edit
point; checkpoint export test.

**Risks & mitigations.** Overselling tamper evidence (docs + PRD 18 wording).

**Decision.** D-19.13 (checkpoint interval + export format).

### E2. `verify-store --repair` (operator-initiated) · M13 (M12 workload) · #180

**Why (evidence).** F4 recovery says "preserve evidence; re-initialize store; investigate," and
the tamper-response runbook assumes an operator procedure — but no tooling exists. Today a corrupt
chain is detectable and unfixable.

**Behavior.** `agentwatch verify-store --repair --yes`:
1. refuses without `--yes` (never automatic — NFR-8);
2. copies the damaged store aside as `records.corrupt-<ts>.jsonl` (evidence preserved, hashed);
3. rebuilds a fresh chain from the intact prefix (re-seq, re-hash) into a new file;
4. prints a report: broken `seq`, salvaged count, dropped count, evidence path.

**Data & schema impact.** New repair path in `store.py` + CLI; evidence file uses the same
envelope.

**Security & privacy.** Operator-only, explicit consent; never silently repairs. The evidence copy
is immutable-by-convention and chain-verified before repair.

**Edge cases.** Corruption in the first record (nothing to salvage) → report and refuse to
produce an empty store without `--force`. Multiple breaks → stop at the first, report the rest as
unsalvaged (do not chain across a break). Repair while the daemon runs → refuse (require daemon
stopped).

**Dependencies.** Store verify (M4); E1 checkpoints; runbook `tamper-response.md`.

**Testing.** Corrupt entry k → repair → `verify()` green, records 0..k-1 present, evidence
byte-identical to the pre-repair file; refuse-without-yes; refuse-while-running.

**Risks & mitigations.** Repair used to hide tamper (evidence copy + report + docs).

**Decision.** D-19.14 (repair prevents silent tamper-hiding how?).

### E3. Land the four deferred M4 minors · M5 · #181

**Why (evidence).** The M4 whole-branch review deferred four real hygiene items; two are
correctness-under-concurrency/privacy issues.

**Behavior / detail.**
1. **Atomic + locked retention** — `apply_retention` currently rewrites the whole file unlocked
   and non-atomically; take the append lock, write temp + `os.replace`, and skip the rewrite when
   nothing is purged.
2. **Exact parse-error indexing** — `_load` guesses `broken_at`; report a 1-based line number
   alongside seq and distinguish mid-file vs trailing corruption in `ChainStatus`.
3. **`Mapping` support** — `redact_mapping` accepts `collections.abc.Mapping`, not just `dict`.
4. **Card regex separator** — the credit-card pattern consumes a trailing separator; add a
   lookahead so following text survives.

**Data & schema impact.** No schema change; `ChainStatus` gains a `line` field (additive).

**Security & privacy.** #1 prevents concurrent data loss; #3 broadens the redaction boundary to
the full advertised type.

**Edge cases.** Retention racing append; a malformed middle line shifting indices; an
`OrderedDict`/`MappingProxyType` input; `"4111…1111 ssn"`.

**Dependencies.** M4 store/redaction.

**Testing.** Concurrent append+retention; malformed-middle-line; non-dict Mapping; card-separator.

**Risks & mitigations.** None material.

**Decision.** None new.

### F1. Hook-side spooling to survive daemon outages · M5 · #182

**Why (evidence).** If the daemon is down (crash, upgrade, machine asleep), every hook send
silently fails — the tool call happens and is never recorded. F2's promise ("a miss is recorded,
never dropped") covers hook *errors*, not daemon *outages*. This is the single largest hole in the
"never lose an event" story, and it is invisible to the user.

**Behavior.** On a failed socket send, the hook appends the framed message to a small,
size-bounded spool beside the socket. The daemon drains the spool on (re)start (and periodically),
writing records with their original timestamps, marked recovered.

**Data & schema impact.** Spool file `<socket dir>/agentwatch-spool.jsonl` (or
`<store.path>/spool.jsonl`), newline-delimited frames, size cap (config). Recovered records carry
`security_event.evidence={"recovered": true}` or a `reason`. No envelope change (the daemon
normalizes spooled frames exactly like live ones).

**Security & privacy.** The spool holds raw event frames (possibly secrets) — owner-only 0600,
never exported, capped and drained-then-truncated. Ties to quarantine (B4) and least-privilege
(F5).

**Edge cases.** Spool full → drop oldest with a `hook-error` marker (never silently). Spool while
the daemon is starting (race) → daemon drains before serving. Torn final spool line → parsed
leniently (skip + surface). Machine off mid-spool → frames persist.

**Dependencies.** Hook (shipped); daemon; F2 (dedup); B3 (gap records); F5 (perms).

**Testing.** Daemon-down → hook spools → restart → all events present and marked recovered; spool
cap behavior; torn-line tolerance.

**Risks & mitigations.** Raw-secret retention (owner-only + no-export + drained promptly).
Duplicate delivery (F2).

**Decision.** D-19.15 (spool location + cap + drop policy).

### F2. Exactly-once ingestion (idempotency) · M5 · #183

**Why (evidence).** At-least-once delivery (hook retries, spool drains, duplicate hooks) means the
same tool call can arrive twice; duplicates corrupt counts, cost math, and every detector signal.
Nothing dedups today, and spooling (F1) makes duplication *more* likely, not less.

**Behavior.** The daemon treats `(session_id, span_id, step_type)` as an idempotency key: a
re-delivered frame appends nothing and returns the original entry. Pre/Post pairs are distinct
(step types differ), so both are kept.

**Data & schema impact.** In-memory recent-key set, refreshed from the store tail on start (so
dedup survives restarts). `handle_message` returns the existing record for a duplicate.

**Security & privacy.** None.

**Edge cases.** Legitimately repeated identical calls without a `span_id` (harness omits ids) →
fall back to a content+time hash; document the residual ambiguity. Duplicate arriving after the
key aged out → cap the window (config) and surface if exceeded.

**Dependencies.** F1; store tail read.

**Testing.** Duplicate frame → one record; duplicate after restart → still deduped; Pre/Post of
the same call both retained.

**Risks & mitigations.** Over-dedup of genuinely distinct calls (span-keyed first; document
fallback).

**Decision.** D-19.16 (dedup window + fallback key).

### F3. Export resume cursor (F5) · M5 · #184

**Why (evidence).** F5 promises "records keep accumulating locally; export resumes; no data
lost" — but nothing tracks what was exported, so a restart can double-export or skip. Export
gating (DD-09) is separate; this is position tracking.

**Behavior.** A watermark (`last exported seq`) persists beside the store; export resumes from it
and reports its position in `/healthz` (`export.last_success_at`, position). At-least-once from
the watermark is acceptable if the backend is idempotent; at-most-once is not the goal (data loss
is).

**Data & schema impact.** `export.state.json` (or a store header) with `{last_seq, updated_at}`.
No record change.

**Security & privacy.** Watermark contains no content.

**Edge cases.** Store repaired (E2) / re-chained → watermark seq may be invalid; detect and reset
with a warning (never silently re-export everything without notice). Backend down (F5) →
watermark unchanged, records accumulate.

**Dependencies.** Export (M5); E2; B1 health.

**Testing.** Export/restart test: no record exported twice or skipped; watermark survives restart;
reset-on-repair warns.

**Risks & mitigations.** Backend non-idempotency + at-least-once = duplicates (document; offer
`--from-seq`).

**Decision.** D-19.17 (at-least-once + documented; backend idempotency assumption).

### F4. Store format version marker · M5 · #185

**Why (evidence).** The JSONL envelope has no version. Every day more unversioned data
accumulates; the first format change (responses I1, checkpoints E1, evolution) would mean
guessing. Version markers are free before data exists and expensive after.

**Behavior.** The store's first line is `{"format": 1}` (a genesis marker); `verify()`/`migrate`
read it; an unknown future format is rejected explicitly (never misparsed).

**Data & schema impact.** New genesis line; existing stores without it are treated as format 1
(back-compat) with a one-time note.

**Security & privacy.** None.

**Edge cases.** Empty store (no marker yet) → treat as 1. Marker-only file (no records). Unknown
format → refuse with a clear message.

**Dependencies.** Store (M4); future `migrate`.

**Testing.** Old-store compatibility; unknown-format rejection; marker written on first append.

**Risks & mitigations.** None.

**Decision.** D-19.18 (format 1 semantics).

