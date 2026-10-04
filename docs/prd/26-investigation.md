# PRD 26 — Query & Investigation Experience

**BLUF:** Turn records into answers: transcript import, `diff`, `search`, terminal `view`, live
alerts, session `purge`, and the investigation cookbook.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before
> storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or
> chain verification (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress
> without explicit opt-in (R6); no new runtime dependency without a recorded decision (NFR-5);
> conformance and quality gates apply (NFR-11).

### H1. Import existing Claude Code transcripts · M8 · #192

**Why (evidence).** Every user already has weeks of transcripts on disk — the evidence they wish
they had. A recorder that starts from zero throws away its best first-day demo and its most
compelling answer to "why should I trust this."

**Behavior.** `agentwatch import transcripts [--project PATH] [--since DATE]` transcodes existing
`~/.claude/projects/**/*.jsonl` into records — same redaction, same chain — so `sessions`,
`replay`, and `diff` work on real history immediately. `--dry-run` reports what would be
imported.

**Data & schema impact.** New importer reusing the adapter's record construction; imported
records carry `security_event.evidence={"imported": true, "source": <path>}` and original
timestamps. Never invents data.

**Security & privacy.** Explicit, opt-in, never automatic (D-M). The importer reads raw
transcripts (like the usage extractor A5) with the same allow-list discipline where content is
not being captured; when it does capture content, the active privacy mode and secrets masking
apply. Paths never leave the machine.

**Edge cases.** Huge transcripts → stream, do not load whole. Already-imported (idempotency by
transcript id + mtime) → skip with a note. Malformed transcript lines → quarantine (B4). A
transcript whose format drifted → import the parseable subset and report the rest as a gap. Time
ordering across files.

**Dependencies.** Adapter (shipped); store (M4); redaction/secrets (M4); B4 quarantine; F2 dedup.

**Testing.** Import a fixture transcript reproduces known counts; no unredacted secret appears;
re-running is idempotent; a malformed line is quarantined.

**Risks & mitigations.** Accidentally importing sensitive history a user did not intend (explicit
command, `--dry-run`, per-project scope, docs).

**Decision.** D-M (opt-in only), D-19.32 (import idempotency key).

### H2. `agentwatch diff <a> <b>` · M8 · #193

**Why (evidence).** The question behind every "it worked yesterday" is a behavioral diff: which
tools, in what order, with what outcomes, changed. No standard tool answers this for agent
sessions; it is CUJ-6's core and the debugging loop every user runs.

**Behavior.** A structural diff of two sessions (or the same agent across versions): tool-sequence
alignment, added/removed/failed steps, duration and cost deltas. Text output plus `--json`.
`--explain` (PRD 29) adds a narrative.

**Data & schema impact.** A diff algorithm over record sequences keyed by `(tool.name, step_type,
outcome)` with a sequence-alignment fallback; no schema change.

**Security & privacy.** Operates on already-stored (redacted) records only.

**Edge cases.** Different lengths; reordered steps (alignment, not naive index compare);
versions differ only by prompt (D2 prompt_version surfaces it); one side imported (H1); large
sessions → summarize by default, `--full` for detail.

**Dependencies.** Replay (M5); store (M4); D2.

**Testing.** Diff of two fixture sessions matches a hand-derived result; reorder-vs-change
distinguished.

**Risks & mitigations.** Over-noisy diffs (align + summarize by default).

**Decision.** D-19.33 (alignment algorithm + default verbosity).

### H3. `agentwatch search` / `query` · M9 · #194

**Why (evidence).** At volume, "when did the agent run `rm`?" needs more than raw `grep` over
JSONL but not much more. jq-class composability is the ergonomic bar: records in, records out,
pipe-friendly.

**Behavior.** `agentwatch search --tool Bash --outcome error --session X --since 2d [--json]`,
plus an escape hatch for full queries. Stable `--json` output on every read command.

**Data & schema impact.** A small filter engine over the store; no schema change. Defined,
versioned JSON output.

**Security & privacy.** Read-only over redacted records.

**Edge cases.** No matches (exit 0, empty); invalid filter (usage error, exit 2); `--since`
parsing (relative + absolute); very large results (`--limit`, streaming).

**Dependencies.** Store (M4); I4 project filter; H6 CLI polish.

**Testing.** Filter matrix (each flag and combinations); JSON schema stability; invalid-filter
exit code.

**Risks & mitigations.** Filter language creep (keep it minimal; escape hatch for the rest).

**Decision.** D-19.34 (filter grammar scope).

### H4. `agentwatch view` — terminal timeline (R12 in the terminal) · M8 · #195

**Why (evidence).** The React stack (M7) is parity, but a world-class CLI owns the terminal; the
"local replay viewer" promise (R12) should work with zero services running.

**Behavior.** A read-only TUI: session list → timeline → record detail, with scroll/filter/expand.

**Data & schema impact.** New `agentwatch/view.py` using stdlib `curses`. No schema change.

**Security & privacy.** Read-only; no daemon, no network, no deps (D-L).

**Edge cases.** Tiny terminals; non-TTY (fall back to `tail`/`search` output); broken chain
(flag in the UI, keep viewing valid records); tombstones shown as gaps.

**Dependencies.** Store (M4); replay (M5); C2 tail.

**Testing.** Renders a fixture store; navigation smoke test; non-TTY fallback.

**Risks & mitigations.** A dependency creeping in (stdlib only; D-L).

**Decision.** D-L (stdlib curses only).

### H5. Real-time security signals in `tail` · M8 · #196

**Why (evidence).** A security engineer watching a live run wants to notice the `denied` or
`secret-detected` the moment it happens — not during post-hoc review.

**Behavior.** `tail` highlights security events by default; `--alert` raises a terminal bell or
desktop notification on them. Observation only — no enforcement, ever (PRD 14).

**Data & schema impact.** Rendering + a notification hook; no schema change.

**Security & privacy.** Read-only.

**Edge cases.** Very frequent events → coalesce notifications. Headless → bell only.

**Dependencies.** C2 tail; A2 (denied) / M4 (secret-detected); B1 health.

**Testing.** Alert fires on a security-event record in a fixture stream; coalescing test.

**Risks & mitigations.** Alert fatigue (coalesce + thresholds).

**Decision.** D-19.35 (alert policy).

### H6. CLI polish: completions, teachable help, stable JSON, exit codes · M5 · #197

**Why (evidence).** The difference between "a script" and "a utility" is ergonomics: tab
completion, `--help` that shows examples, machine-readable output on every read command, one
documented exit-code table. This is the gh/kubectl class of polish and it is cheap.

**Behavior.** `agentwatch completions bash|zsh|fish`; example-rich per-command help; `--json` on
all read commands; exit codes documented in one place.

**Data & schema impact.** `.cli-reference.md` updated; completion scripts generated.

**Security & privacy.** None.

**Edge cases.** Shells without completion; `--json` + `--explain` interaction.

**Dependencies.** Every CLI command; J1 protocol docs.

**Testing.** Help tests assert examples; completions generate without error; `--json` schema.

**Risks & mitigations.** Inconsistent flags across commands (a shared read-command base).

**Decision.** D-19.36 (shared read-command options).

### J3. Investigation cookbook · M9 · #205

**Why (evidence).** World-class tools teach workflows, not flags (ffmpeg's docs, git's book).
agentwatch's aha moment is an investigation — "the agent ran `rm` in a worktree at 14:03" — and
no doc walks one end-to-end. It doubles as demo material (M8) and launch content.

**Behavior.** 3–5 reproducible narratives (loop found, secret caught, denied call reviewed):
record → search → replay → verify → evidence → (optionally explain, PRD 29), each with the exact
commands and a seed dataset.

**Data & schema impact.** `docs/examples/investigations/*.md`; seed fixtures.

**Security & privacy.** Uses the demo/seed data (no real secrets).

**Edge cases.** Commands must stay valid as the CLI evolves (link-check + a runnable script where
possible).

**Dependencies.** H2/H3/H4; seed (M8).

**Testing.** Each narrative reproducible against seed data (script or test).

**Risks & mitigations.** Docs drift (tie examples to the seed + CI).

**Decision.** None new.

### I5. `agentwatch purge <session-id>` (right to erasure) · M10 · #202

**Why (evidence).** Retention and erasure are different obligations; one session may need to be
gone (contains something it should not, a subject request, a policy). Today the only lever is
deleting the whole store. PRD 15's invariant ("purge tombstones, never silently removes") already
defines the honest shape.

**Behavior.** `agentwatch purge <session-id> [--yes]` tombstones every record of that session
(payload dropped, chain links preserved, a purge record written), chain-safe and reported by
`verify`.

**Data & schema impact.** Reuses the retention tombstone envelope; a `purge` marker record
records who/why (operator, timestamp).

**Security & privacy.** Explicit consent (`--yes`); never hard-deletes; the tombstone proves the
purge happened. The `--reason` is stored (metadata only).

**Edge cases.** Session not found (exit 1); partial session across resumed ids (I3 — purge all
linked ids); purge while the daemon runs (coordinate via the store lock or require stop).

**Dependencies.** Retention tombstones (M4); E2; I3.

**Testing.** Purge tombstones only that session; other sessions intact; `verify()` green; a purge
record present.

**Risks & mitigations.** Mistaken purge (require `--yes` + session id; report the purged count).

**Decision.** D-K (tombstone, never hard delete).

