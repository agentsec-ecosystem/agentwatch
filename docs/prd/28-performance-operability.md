# PRD 28 — Performance & Operability

**BLUF:** Publish performance honestly and operate safely: async hooks, durability modes, offline proof, service units, soak, file posture, bounded logs.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

### F5. Least-privilege store file posture · M13 (M12 workload) · #186

**Why (evidence).** The socket is 0600 (M3), but the store directory and records file use default
permissions. Records are behavior evidence; on a shared machine, world-readable-by-default is the
wrong posture for an audit trail.

**Behavior.** Store directory `0700`; records/quarantine/spool/log files `0600` — enforced at
creation, checked by `doctor` (C1), reported in `/healthz` (B1).

**Data & schema impact.** Mode enforcement in store/quarantine/log creation; a `doctor` check.

**Security & privacy.** Directly reduces exposure of redacted-but-sensitive evidence.

**Edge cases.** Pre-existing files with loose modes → reported, optionally tightened (do not
silently chmod others' files beyond our store). Umask interactions. Filesystem without POSIX
modes (Windows is later).

**Dependencies.** Store (M4); B4/F1/F6 create the other files; C1.

**Testing.** Creation asserts 0700/0600; doctor flags a loose mode.

**Risks & mitigations.** Over-restricting breaks an operator's own access (documented).

**Decision.** None new.

### F6. Bounded, rotated daemon logs · M13 (M12 workload) · #187

**Why (evidence).** `daemon.log` grows unbounded. NFR-3 bounds the record store, but the daemon's
own log is a slow disk leak — the kind that eventually eats the very disk the caps protect.

**Behavior.** `daemon.log` rotates at a cap (e.g., 5 MB × 2 files); the cap and current size are
reported by `doctor`/`/healthz`.

**Data & schema impact.** Logging setup in `install.start_daemon`/daemon.

**Security & privacy.** Logs may contain paths and error text; owner-only (F5); no record content.

**Edge cases.** Rotation mid-write; disk full during rotation → keep the newest, drop the oldest,
surface. Concurrent writers (daemon + hook diagnostics) → single-writer rule or per-writer files.

**Dependencies.** Daemon; F5; B1.

**Testing.** Rotation at cap; size reported; oldest dropped.

**Risks & mitigations.** None material.

**Decision.** D-19.19 (cap sizes).


### P1. Non-blocking hooks + a published latency number · M5 · #217

**Why (evidence).** NFR-1's "≤5 ms/step" is an in-process SDK figure. The hook path pays a Python
spawn (~30–80 ms) **inside the agent's tool-call critical path** on every Pre/Post call —
invisible to us, very visible to the user. Claude Code supports `"async": true` (run the handler
in the background, do not block); our hook is already fire-and-forget, so blocking buys nothing
and costs latency.

**Behavior.** Installed hook handlers run async by default; `--sync-hooks` opts out for debugging.
A benchmark measures the real per-call overhead (spawn → socket send → exit) and publishes it.

**Data & schema impact.** `install.py` writes `"async": true` on handlers; a new benchmark test.

**Security & privacy.** Async changes ordering: a `Pre` frame can theoretically land after its
`Post` on a loaded machine. The daemon's `_pending_pre` logic already synthesizes a `hook-error`
for post-before-pre; with async on, decide whether out-of-order should be downgraded to a benign
note (recommended: track and correlate, do not error on a known out-of-order arrival — D-C).

**Edge cases.** Post arrives first under load; a Pre never arrives (async process killed); hooks
that must observe ordering for security events (denied). All covered by a deliberate ordering
test.

**Dependencies.** `install.py` (shipped); daemon pairing; resource-cost docs.

**Testing.** Benchmark under a stub daemon stays under the documented async ceiling; an
out-of-order Pre/Post test; `--sync-hooks` still works.

**Risks & mitigations.** Ordering regressions (explicit test; correlation key reuse).

**Decision.** D-C (async default), D-19.28 (out-of-order semantics).

### K1. Adaptive durability (fsync policy) · M13 (M12 workload) · #206

**Why (evidence).** Every append fsyncs — correct but expensive at volume; integrity at rest is
provided by the chain, not by fsync. Durability should be an explicit, measured choice, never
hidden.

**Behavior.** A configured durability mode: `per-record` (default, safest), `per-checkpoint`, or
`on-idle`; `/healthz` reports the active mode and the write cost.

**Data & schema impact.** Config key; store append respects the mode; benchmark documents the
tradeoff.

**Security & privacy.** A weaker mode risks losing the last few unreconciled appends on power
loss — documented, never silent; the chain still detects tampering with what is written.

**Edge cases.** Crash in `on-idle` loses the unflushed tail → the gap record (B3) accounts for
it. Switching modes at runtime.

**Dependencies.** Store (M4); B1 health; resource-cost docs.

**Testing.** Each mode asserts its expected flush behavior; default remains per-record.

**Risks & mitigations.** Silent data loss under a weak mode (documented; default safe).

**Decision.** D-N (default stays per-record).

### K2. Prove local-first in CI (no-network E2E) · M13 (M12 workload) · #207

**Why (evidence).** R6/NFR-9 ("no network required") is a guarantee, but nothing tests
install → record → verify → replay with networking disabled. A stray telemetry call or a
dependency phoning home would be reputationally fatal for a security tool.

**Behavior.** A CI job runs the full E2E with networking disabled; a dependency audit gate flags
any runtime dependency capable of egress.

**Data & schema impact.** CI workflow + audit config.

**Security & privacy.** This *is* the privacy guarantee made testable.

**Edge cases.** Optional extras (OTLP exporter) legitimately use the network — the gate must
distinguish core (no egress) from opt-in extras.

**Dependencies.** E2E (M8); CI (M1).

**Testing.** E2E passes offline; audit fails on a new egress-capable core dep.

**Risks & mitigations.** False confidence if the sandbox leaks network (verify the block works).

**Decision.** D-19.29 (how the network is disabled in CI).

### K3. Optional service supervision (`init --service`) · M13 (M12 workload) · #208

**Why (evidence).** F1's detection story assumes a supervisor restarts the daemon; today it is a
bare detached process — a reboot or crash ends recording until a human notices. F1's recovery row
depends on supervision that does not exist.

**Behavior.** `agentwatch init --service` generates a launchd (macOS) / systemd user unit (Linux)
that restarts the daemon; `uninstall` removes it. Opt-in only.

**Data & schema impact.** Unit-file templates; install/uninstall wiring.

**Security & privacy.** A user-level unit (no root); the service runs the same owner-only daemon.

**Edge cases.** macOS vs Linux paths; existing unit of the same name; user without systemd.
`--no-daemon` interaction.

**Dependencies.** `install.py`; F1 gap records.

**Testing.** Unit-file generation for both platforms; uninstall removes it; idempotent install.

**Risks & mitigations.** Conflicting with a user's own supervision (opt-in; clear name).

**Decision.** D-19.30 (unit names + scope).

### K4. Nightly soak test (NFR-7 groundwork) · M13 (M12 workload) · #209

**Why (evidence).** Scale claims ("10k+ traces/day") are v0.2.0, but the store's shape under
sustained load — file size, verify time, retention behavior, daemon memory — should be known
before users ship real data into v0.1.0. Publish, don't hope.

**Behavior.** A nightly job generates sustained traffic and asserts bounded memory, verify time,
and store size vs caps; results are published in `resource-cost.md` next to the latency number
(P1).

**Data & schema impact.** A soak harness + nightly CI job + docs table.

**Security & privacy.** Uses synthetic data only.

**Edge cases.** Retention kicking in mid-soak; checkpoints (E1); dedup (F2) under load; F3 cap.
These interactions are the point.

**Dependencies.** F1/F2/E1/K1; retention (M4).

**Testing.** Soak stays within documented bounds; a regression opens an issue.

**Risks & mitigations.** Nightly flakiness (thresholds + trend, not a single run).

**Decision.** D-19.31 (bounds + reporting cadence).

