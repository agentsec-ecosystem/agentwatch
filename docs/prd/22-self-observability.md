# PRD 22 — Recorder Self-Observability

**BLUF:** The recorder proves what it is doing: `/healthz`, `doctor`, `tail`, and continuous chain verification.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### B1. Serve `/healthz` and self-observability (NFR-12, pulled forward) · M5 · #170

**Why (evidence).** PRD 13 specifies a complete health contract so an operator can tell a clean
run from "couldn't read the run" (the AgentObservatory lesson). The daemon already holds every
field — chain status, store path/size, self-test result, hook activity — but serves nothing.
`configuration.py` already reserves `health.endpoint` (`127.0.0.1:9100`). Landing it early makes
every later field test measurable and lets `status` stop being a config dump.

**Behavior.** `GET http://127.0.0.1:9100/healthz` returns JSON:
- `state`: `recording` | `degraded` | `stopped` — and **why** (the stop reason).
- `daemon`: `pid`, `uptime_s`, `version`.
- `store`: `path`, `records`, `size_mb`, `chain_ok` (bool), `last_append_at`.
- `export`: `enabled`, `endpoint`, `last_success_at`, `last_error`.
- `redaction`: `mode`, `self_test_passing` (bool).
- `hooks`: per-harness `installed`, `last_fire_at`, `errors` (count).
- `gaps`: recent recording-gap events (F1/F2/F8 from PRD 17).

`agentwatch status` prints the human view of the same truth; when the daemon is down it prints
`state=stopped` with the reason (the one state HTTP cannot serve). PRD 13's OTel self-metrics
(`agentwatch.records.stored`, `agentwatch.gaps`, `agentwatch.export.errors`,
`agentwatch.chain.broken`, `agentwatch.self_test.passing`) are emitted on the same exporter when
export is enabled.

**Data & schema impact.** New module `agentwatch/health.py` (ThreadingHTTPServer, localhost
bind only). A thread-safe `HealthSnapshot` in the daemon, updated by `handle_message`,
`_append`, the chain verifier, and the self-test. No record-schema change.

**Security & privacy.** Bind to loopback only; no auth in v0.1.0 (a unix socket is an
alternative, D-19.6). The payload contains **no record content** — counts, timestamps, paths,
booleans only. Paths are local and operator-visible; document that `/healthz` is not to be
exposed off-host.

**Edge cases.** Port already in use → daemon logs and continues recording (health is
best-effort, never fatal — recording must not depend on the endpoint). Broken chain → `degraded`
or `stopped` per PRD 13. No hooks ever fired → `hooks.installed=true, last_fire_at=null` →
`degraded`. Self-test failing → `degraded` + `export` blocked. Concurrent readers → snapshot is
copied under a lock.

**Dependencies.** Daemon (shipped); selftest (M4, shipped); store verify (M4, shipped); export
(M5) for `export.*` and metrics; F1/F8 for `gaps`.

**Testing.** Health contract test asserting every PRD 13 field and its type; state transitions
(recording→degraded on broken chain; stopped on store-full F3); localhost-only bind assertion;
port-in-use does not stop recording.

**Risks & mitigations.** Health endpoint becoming an attack surface (loopback + no secrets +
documented). Divergence between `status` and `/healthz` (single snapshot source).

**Decision.** D-19.6 (HTTP loopback vs unix socket for health).

### C1. `agentwatch doctor` · M5 · #175

**Why (evidence).** NFR-4 promises first-run ≤15 min, but failure is silent: hooks missing, daemon
dead, socket moved, config invalid. The runbook's Troubleshoot section is a manual checklist; a
lost first-run is a lost user. Every check already has an implementation somewhere in the tree.

**Behavior.** One command runs an ordered checklist and prints `PASS`/`FAIL` + a one-line fix
hint per check; exit 0 only if all pass. `--json` emits the same data for scripts/CI.
Checks:
1. config loads (fail-closed, F7) and prints the resolved values;
2. hooks installed (project and/or user; warn if both or neither);
3. daemon alive and the socket accepts a probe connection;
4. the hook entry point resolves and is executable;
5. store `verify()` green (chain);
6. redaction self-test passing;
7. store path writable and free disk ≥ `max_size_mb`;
8. retention settings sane (`retention_days ≥ 1`);
9. version printed (self-report; no phone-home — C7).

**Data & schema impact.** New `agentwatch/doctor.py` composing `configuration`, `install`,
`store`, `selftest`. No schema change.

**Security & privacy.** Reads local config/paths only; no network. Must not print secrets from
config (redact values before printing).

**Edge cases.** Daemon down is a `FAIL` with "run `agentwatch init`/start daemon", not a crash.
No store yet is a `PASS`-with-note ("no records yet"). Partial install (hooks but no daemon) is a
precise, actionable message.

**Dependencies.** M1–M4 shipped primitives; B1 health (doctor can prefer `/healthz` when up).

**Testing.** One broken precondition per check, asserting `FAIL` + the right hint; all-green run
exits 0; `--json` schema test.

**Risks & mitigations.** Doctor drifting from real failures (tie checks to the same functions
the daemon uses; add a doctor check whenever a new failure mode lands).

**Decision.** None new.

### C2. `agentwatch tail [--session-id …] [-f]` · M5 · #176

**Why (evidence).** Before the operator UI (M7) there is no way to *see* recording working —
critical for demos (M8), field tests (M14), and user trust. Read-only, zero risk.

**Behavior.** Prints one line per record, most recent last, e.g.
`14:03:12 · sess-9f2 · observe · Bash · ok · 42ms`. `-f` follows (1 s poll) until interrupted;
`--session-id` filters; tombstones and parse errors are skipped with an inline note.

**Data & schema impact.** New `agentwatch/tail.py`; reverse-seeks the JSONL envelope. No schema
change.

**Security & privacy.** Read-only; honors the store's permissions; displays only fields already
stored under the privacy mode (never re-reads raw transcripts).

**Edge cases.** Tail of a store being written concurrently (tolerate a partial final line);
store absent; tombstones; broken chain (print a warning line, keep tailing valid records).

**Dependencies.** Store envelope (M4); A2/A3 enrich the lines (denied/reason).

**Testing.** Line rendering against a fixture store; follow mode interruptible; concurrent-write
tolerance.

**Risks & mitigations.** None material (read-only).

**Decision.** None new.


### G2. Continuous chain verification · M13 (M12 workload) · #189

**Why (evidence).** Chain integrity is checked at daemon start or on demand; a break at hour 2 of
a session is invisible for hours. Late tamper evidence is weak evidence; PRD 17 wants failures
surfaced, not discovered.

**Behavior.** Incremental verification from the last checkpoint after each append (O(1)
amortized); a break flips `/healthz` `state` to `degraded`/`stopped` immediately.

**Data & schema impact.** The store keeps a running verify cursor; the daemon consults it; a
periodic full verify (hourly / every K appends) catches an edit the incremental path would miss.

**Security & privacy.** None (booleans + seq).

**Edge cases.** An earlier record edited after its incremental check → caught by the periodic
full verify. Large store → bound per-append work. Repair (E2) resets the cursor.

**Dependencies.** Store (M4); E1 checkpoints; B1 health.

**Testing.** Mid-session tamper surfaces without a manual verify; per-append overhead bounded
(cross-check K4).

**Risks & mitigations.** Incremental verify missing an earlier edit (periodic full verify).

**Decision.** D-19.21 (full-verify cadence).

