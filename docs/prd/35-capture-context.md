# PRD 35 — Capture Context

**BLUF:** Complete the record's context so "what happened" is answerable: **who authorized** each call (S14),
whether the context was **compacted** (S15), what **revision** the agent acted on (S16), what **OS principal**
it ran as (S29), and a one-command **demo** that proves the pipeline (S31).

**Status:** proposed (2026-10-03) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

The common discipline across these items: **record what the harness actually exposes, and record `unknown`
rather than infer.** An honest `unknown` is useful; a guessed value is a false audit record, which is worse
than no field.

### S14. Approval provenance — record *who authorized* each call · v0.1.0 · (new)

**Why.** A2 records denied calls and `outcome=ok` covers everything else — silently merging three different
facts: *a human explicitly approved this `rm -rf`*, *an allow-list auto-approved it*, and *it needed no
permission*. For an audit trail that is the most important distinction in the record: the first question about
a destructive action is **"did a human say yes?"** Checked against the code, `install.py` registers seven hook
phases and the only permission-related one is `PermissionDenied`; the adapter has `permission-denied` and no
notion of approval. The product records every refusal and no consent.

**Behavior.** An `approval` dimension on the record — `user | auto | not-required | denied | unknown` — derived
from the permission surface the harness exposes (the `Notification` hook fires on a permission prompt; a
`PreToolUse` followed by prompt-then-proceed differs from one that is not). Surfaced in `replay`,
`search --approval user`, `impact` (S3), and the evidence bundle.

**Data & schema impact.** New record field (additive, minor bump), defaulting to `unknown` on legacy reads.

**Security & privacy.** Recording only — it observes the authorization decision, never makes one.

**Edge cases.** Where the harness cannot distinguish `user` from `auto`, the value **must** be `unknown`, never
guessed (F8's reject-never-coerce discipline applied to derivation). A denied call → `denied`. No permission
surface → `unknown`.

**Dependencies.** A2, the `Notification` hook phase, N4 (per-harness derivation rules).

**Testing.** A prompt-then-proceed fixture yields `user`; an auto-approved fixture yields `auto`; a harness with
no exposed surface yields `unknown`.

**Risks & mitigations.** Over-claiming consent from weak evidence → `unknown` default; derivation rules
published per harness version.

**Decision.** New — field name/values and the per-harness derivation table.

### S15. Capture context compaction · v0.1.0 · (new)

**Why.** Compaction is the most common cause of the behavior users complain about most — the agent "forgets,"
redoes work, re-reads files, contradicts an earlier decision — and it is invisible in the record.
`install.py` registers no `PreCompact` phase, so a session compacted three times is indistinguishable from one
that was not. Every loop/retry detector in L1 is missing a variable: a retry loop *immediately after a
compaction* is a different finding from the same loop without one.

**Behavior.** Register the `PreCompact` hook and record a `context-compacted` step — metadata only (timestamp,
trigger `auto|manual`, token count before/after if exposed). `replay` and `view` show compaction boundaries
inline; `diff` can attribute a behavioral change to one; L1 detectors take it as input.

**Data & schema impact.** One more hook phase + a metadata-only step; no content.

**Security & privacy.** Pure metadata about the *container*, never the content — no prompt text, no summary,
nothing from the compaction payload. Outside the A5 sensitive-read-path discussion entirely.

**Edge cases.** Missing token counts → omitted, not zeroed. An unknown trigger value → `unknown`. Repeated
compactions → one step each, not coalesced.

**Dependencies.** M3 adapter, `EVENT_PHASES`, L1 (consumer).

**Testing.** A `PreCompact` event yields one `context-compacted` step with the trigger; no payload content is
stored; replay shows the boundary.

**Risks & mitigations.** The hook payload shape is undocumented and may drift → allow-list the fields read and
let S19 report anything unexpected.

**Decision.** New — metadata field allow-list and whether `PreCompact` is on by default.

### S16. Capture the revision the agent acted on · v0.1.0 · (new)

**Why.** "What did the agent do last Tuesday?" is half an answer without **"to what?"** The record carries
`project` (cwd) and `prompt_version` (a CLAUDE.md digest) — nothing identifies the state of the codebase. A
bundle that says "the agent edited `billing/charge.py` at 14:03" cannot be correlated to the repository unless
someone knows which commit was checked out and whether the tree was dirty. This is the cheapest missing piece
of forensic context: one `git rev-parse` at session start.

**Behavior.** At `SessionStart`, record an environment snapshot: git commit SHA, branch, dirty-tree boolean,
harness name+version, OS/arch, agentwatch version. Metadata only; no remote URLs (they can carry credentials),
no env-var values.

**Data & schema impact.** New metadata-only session-start observation; additive.

**Security & privacy.** Local read, metadata only, no egress.

**Edge cases.** Non-git project → `vcs: none` (distinguishing "we did not look" from "there was nothing"); a
`git` failure → `vcs: unavailable`, never blocks; captured once per session, not per call.

**Dependencies.** A1 session boundaries, P1 async hooks.

**Testing.** A git fixture records SHA/branch/dirty; a non-git fixture records `vcs: none`; a failing git
records `unavailable` and the hook still exits 0.

**Risks & mitigations.** A `git` invocation adding latency → runs in the async hook path (P1); failure never
blocks.

**Decision.** New — snapshot fields and the `vcs` enum.

### S29. Capture the OS principal · v0.1.0 · (new)

**Why.** The record identifies the *agent* and not the *account it acted as*. For a security audit that is
backwards: "agent `claude-code` deleted the table" matters far less than "it ran as `deploy@ci-runner-7`, uid
1001, non-interactive." On a shared box, in CI, or in a container, the OS principal is the identity that maps
to a human and to an access grant — and it is free to capture.

**Behavior.** At session start, record uid/username, hostname, pid/ppid, whether stdin is a TTY, and a
`context: interactive | headless | ci` classification (CI detected from conventional env-var names, names
only). No env-var values, no home paths.

**Data & schema impact.** New metadata-only session-start observation, merged with S16's snapshot.

**Security & privacy.** Local metadata, no egress; identity of the *process*, not the person. Usernames and
hostnames are mildly identifying → included in the privacy-mode matrix so `metadata-only` installs can drop
them.

**Edge cases.** `headless` also makes G4's trust-gated headless gap self-diagnosing instead of guessed. No
TTY → `headless`. CI env var present → `ci`.

**Dependencies.** A1 session boundaries, S16 (same snapshot), S2.

**Testing.** A simulated CI env classifies `ci`; a dropped-principal config omits the fields; no env-var
*value* is stored.

**Risks & mitigations.** Mildly identifying metadata → part of the privacy-mode matrix; documented choice.

**Decision.** New — which fields `metadata-only` drops.

### S31. `agentwatch demo` — prove the pipeline in 30 seconds · v0.1.0 · (new)

**Why.** R2 promises "fresh machine → first recorded tool call ≤15 min," and the 15 minutes are mostly waiting
to find out whether it worked. After `init`, confirming hook→daemon→redaction→chain→verify means using Claude
Code and hoping. `doctor` checks the environment and `status` reports state; neither exercises the pipeline.
The anxiety gap between installing and trusting is where adoption is lost, and it is closable with a synthetic
session.

**Behavior.** `agentwatch demo` synthesizes a handful of events through the **real** hook → daemon → store path
(including one denial, one secret to be redacted, one error), then prints the resulting timeline, the chain
verdict, and the redaction result, with `--purge` to remove it. One command that says "this works, here is the
proof," using the live code path rather than fixtures.

**Data & schema impact.** Records marked `producer.kind: demo` (S26) so synthetic data can never be mistaken
for evidence; `--purge` leaves the store as found.

**Security & privacy.** Local, synthetic, self-cleaning.

**Edge cases.** Daemon not running → demo states the failure and its cause (it is a diagnostic). A real store
present → demo records are excluded from S2 coverage and S1 bundles.

**Dependencies.** M3 hook/daemon, M4 store, S26, J3 seed data.

**Testing.** `demo` records chain and verify; `--purge` removes exactly the demo records; a coverage run
excludes `producer.kind: demo`.

**Risks & mitigations.** Demo data polluting a real store or a coverage calc → the producer field plus
exclusion from S2/S1.

**Decision.** New — demo event set and `--purge` scope.
