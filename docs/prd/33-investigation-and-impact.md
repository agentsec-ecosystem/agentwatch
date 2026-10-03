# PRD 33 — Investigation & Impact

**BLUF:** Convert a recorded session into the answers an investigator actually asks: **what changed in the
world** (change footprint), **who touched this file**, **when did anything happen**, **what did it cost**,
**what did the subagents do**, and **was a denial followed by a workaround** — plus a stable behavior
fingerprint to compare, dedupe, and detect drift.

**Status:** proposed (2026-10-03) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Every item is a **descriptive** read over already-redacted records. None scores, ranks, or renders a verdict —
that line is PRD 14's, and this PRD states it explicitly because several views come close to it.

### S3. `agentwatch impact` — the change footprint (blast radius) of a session · v0.1.0 · (new)

**Why.** After an incident nobody wants 400 ordered tool calls; they want **"what did it touch, and is any of
it still touched?"** The canonical incident in PRD 01 (a database deletion) is answered by a footprint, not a
timeline. agentwatch stores `Write`/`Edit`/`Bash`/`MultiEdit` arguments, `tool.response` (I1), and outcomes,
and derives none of it. Replay answers *what happened*; `diff` answers *what changed between runs*; nothing
answers *what changed in the world*.

**Behavior.**
```sh
agentwatch impact <session-id> [--json] [--since 2d]
```
Grouped, deduplicated footprint: files written/edited/deleted; commands with side effects (package installs,
migrations, service restarts, destructive verbs); network destinations observed (hosts in `curl`/`wget`/
WebFetch/MCP endpoints); VCS actions; credential-adjacent touches (`.env`, `~/.aws`, keychain); a blast-radius
summary with counts and a "widest action" line.

**Data & schema impact.** Pure derivation; a shared argument classifier (also used by S18, S23, S25). No
record change.

**Security & privacy.** Derived read over redacted records; no enforcement, no scoring. Classification is
**deterministic and published** — a versioned table of patterns per class with `confidence: exact | heuristic`
per entry. Descriptive, never a verdict.

**Edge cases.** Shell parsing is a bottomless pit → a small documented classifier with a surfaced
`unclassified` bucket; never claim completeness. A file touched outside `project` → attributed but flagged.

**Dependencies.** I1 tool responses, store (M4), L1 detector conventions (reuse the evidence shape).

**Testing.** Two fixture sessions produce hand-derived footprints; a reorder vs a change is distinguished;
every classification carries exact/heuristic.

**Risks & mitigations.** Risk scoring creeping in → hard rule: facts only; "exfiltration" is
agentpolicy's/human's judgment.

**Decision.** D-32.1 — classifier pattern table + `unclassified` policy.

### S17. `agentwatch tree <session>` — the subagent fan-out · v0.1.0 · (new)

**Why.** A4 already captures subagent attribution (`agent_id`/`agent_type` → identity) and nothing renders the
structure. A session dispatching six parallel subagents is stored as a flat, interleaved stream where nobody
can tell which subagent did what, burned the tokens, or failed. The data is a tree; every view is a list.

**Behavior.** `agentwatch tree <session-id> [--json] [--by-cost]` printing parent → subagent fan-out with
per-node tool counts, outcomes, duration, tokens; parallel branches as siblings with their own timelines.

**Data & schema impact.** Pure derived read over A4 attribution; no record change.

**Security & privacy.** Derived read only.

**Edge cases.** No subagents → render a single root, never error; an orphan child (missing parent) → attached
to the root with a note.

**Dependencies.** A4 (shipped), S6 (cost column).

**Testing.** A fixture with two parallel subagents renders two siblings with correct counts; a no-subagent
session renders one root.

**Risks & mitigations.** Deep recursion on pathological nesting → bounded depth with a note.

**Decision.** D-32.2 — token/cost aggregation across a branch.

### S18. `agentwatch blame <path>` — the file-centric reverse index · v0.1.0 · (new)

**Why.** S3 answers *session → what did it touch*. The question that arrives first is the inverse: you find
something wrong in the repo and ask **"which agent touched this file, when, in which session?"** — git blame
for agent activity, including edits later overwritten, which git cannot show. Today it is `search --tool Edit`
plus grep plus manual correlation.

**Behavior.** `agentwatch blame <path> [--since 30d] [--json]` lists every record whose arguments touched the
path, newest first, with session/agent/tool/outcome/timestamp; `--sessions` jumps into `replay`/`impact`.

**Data & schema impact.** Reuses S3's argument classifier; no record change.

**Security & privacy.** Derived read over redacted records.

**Edge cases.** Relative vs absolute paths and the `--project` base are normalized against the project root;
report `confidence: exact | heuristic` (a path in a `Write` argument is exact; one inside a shell command is
heuristic). Symlinks/`~`/`../` documented as limits.

**Dependencies.** S3 classifier (shared), I4 project filter.

**Testing.** Two sessions touching one path list newest-first; a heuristic shell-embedded match is labelled;
a path outside the project is not falsely matched.

**Risks & mitigations.** Path-normalization false negatives → normalize both sides against the project root
and document the limits.

**Decision.** D-32.3 — normalization rules (symlink/worktree handling).

### S24. `agentwatch at <time>` — the cross-session time window · v0.1.0 · (new)

**Why.** Every read command is session-scoped, and **no incident arrives as a session id** — it arrives as
"prod broke around 2pm." The responder's first move is *all* agent activity in a window, across every project
and session, ordered by time; that view does not exist.

**Behavior.** `agentwatch at "2026-10-02 14:00" [--window 30m] [--json]` — every record in the window from all
sessions, with session/project/agent/tool/outcome/approval (S14), plus a header summarizing which sessions
were active and whether recording had a gap in the window (S2/S5).

**Data & schema impact.** Sort over stored records; no record change.

**Security & privacy.** Derived read.

**Edge cases.** Timezone: accept explicit offsets, default to local, echo the resolved UTC range in the output
(Q12). A window with no records → the header distinguishes "nothing happened" from "nothing was watched."

**Dependencies.** Store (M4), S2 coverage windows, S5, S14.

**Testing.** Two sessions in one window render time-ordered; a gap in the window is stated; an offset input is
echoed as the resolved UTC range.

**Risks & mitigations.** Timezone confusion → explicit offsets + echoed resolved range.

**Decision.** D-32.4 — window default and header gap semantics.

### S25. Surface denied-then-retried sequences · v0.1.0 · (new)

**Why.** A2 records denied calls as isolated events. What matters is the *sequence*: denied, then a second
attempt at the same end by another route — `rm` refused, then a Python `unlink`; a blocked path, then a
symlink. Whether that is working around an obstacle or something worse, it is the most security-relevant
pattern a coding-agent record can contain, and it is invisible when denials are listed one by one.

**Behavior.** For each `denied` record, record the next N calls in the session as its follow-up window and
surface `denied → followed by` in `replay`, `impact`, and the evidence bundle. A detector input, **not** a
detector verdict.

**Data & schema impact.** Derived adjacency; no record change.

**Security & privacy.** Observation only; sequence adjacency is arithmetic, not inference.

**Edge cases.** Denial at session end → empty follow-up window, stated. Multiple denials → each gets its own
window. Neutral naming; no severity field.

**Dependencies.** A2 (shipped), L1, S3.

**Testing.** A fixture denial followed by a different-route retry surfaces the follow-up; a denial with no
follow-up is shown with an empty window.

**Risks & mitigations.** Read as an accusation → neutral naming ("followed within N calls by…"), no severity;
leave scoring to L1/agentpolicy.

**Decision.** D-32.5 — follow-up window size N.

### S7. Session behavior fingerprint — a stable hash of what the agent did · v0.1.0 · (new)

**Why.** A deterministic digest over the normalized action sequence (ordered `(tool.server, tool.name,
step_type, outcome)` tuples, arguments excluded) pays off four times: identical-run detection, a cheap drift
primitive for the trailing-baseline idea (#66), a fast pre-filter for `diff` (equal fingerprints need no
diff), and a stable identifier for the field test and cookbook to refer to a *behavior*, not a session id.
PRD 15 has no behavioral-identity concept; everything is per-execution and useless for comparison.

**Behavior.** `behavior_digest` on the session summary + `agentwatch sessions --group-by-behavior`.
Normalization rules published and versioned; the digest carries its version (`bd1:<sha256>`).

**Data & schema impact.** New derived summary field; normalization published + versioned. No record-schema
change.

**Security & privacy.** Pure derivation; no content.

**Edge cases.** Over-sensitive normalization makes every run unique → tested against the golden corpus (I2)
and versioned so it can be tightened. A single-record session → still produces a digest.

**Dependencies.** Replay (M5), I2 golden corpus.

**Testing.** Two identical action sequences share a digest; an added tool changes it; the digest version is
embedded.

**Risks & mitigations.** Normalization over-sensitivity → publish + test against the golden corpus + version.

**Decision.** D-32.6 — what is normalized (server/name/step/outcome) and the version prefix.

### S33. Capture the human interrupt · v0.1.0 · (new)

**Why.** One of the loudest signals a coding agent produces is a person hitting escape. An abort mid-tool-call
is a judgment — *that was wrong, stop* — and the clearest labelled data the system will see about agent
quality. It is absent from the record: an interrupted session looks like one that simply ended. Every L1
anomaly signal is trying to infer what the user already told the harness directly.

**Behavior.** Record `interrupted` as a distinct session-end reason (and per-record where a tool call was cut
short), separating `completed`, `interrupted-by-user`, `errored`, `abandoned`. Surface in `sessions`, `diff`,
and as a detector input.

**Data & schema impact.** New session-end reason value / step metadata; no content.

**Security & privacy.** Recording only.

**Edge cases.** `abandoned` (no end event) must stay distinct from `interrupted` (explicit stop) — collapsing
them turns a crash into a user verdict. The harness may not expose interrupts cleanly → record `unknown`
rather than infer (S14's discipline).

**Dependencies.** A1 session boundaries, EVENT_PHASES, L1.

**Testing.** An explicit interrupt yields `interrupted-by-user`; a session with no end event yields
`abandoned`; a session with an error yields `errored`.

**Risks & mitigations.** Inferring an interrupt from weak evidence → `unknown` default, derivation rules
published per harness version (N4).

**Decision.** D-32.7 — end-reason vocabulary and where it is carried.

### S37. `agentwatch digest` — the local weekly readout · v0.1.0 · (new)

**Why.** The top success metric is "installs still recording after 30 days (>70%)," and nothing gives a user
a reason to look again. A recorder that is never read becomes one that gets uninstalled. A digest is the
retention mechanism that respects the no-telemetry rule completely: generated locally, shown locally, shared
only if the operator chooses.

**Behavior.** `agentwatch digest [--since 7d]` — sessions, tool mix, cost (S6), denials, security events,
capture rate (S2), notable sequences (S25), and anything new in the inventory (S4) — rendered as short
markdown suitable for pasting into a team channel by hand.

**Data & schema impact.** Derived read; no record change.

**Security & privacy.** Local, derived, opt-in by invocation. No scheduling, no notification, no egress —
the moment agentwatch sends this anywhere itself, it crossed the silent-telemetry line.

**Edge cases.** No activity in the window → "no agent activity recorded," not an empty doc. Gaps present →
stated in the digest (S2).

**Dependencies.** S2, S4, S6, S25.

**Testing.** A seeded week produces a digest naming sessions/cost/gaps; nothing is written to the store or
sent anywhere.

**Risks & mitigations.** Becoming a reporting product → one command, markdown out, no delivery mechanism.

**Decision.** D-32.8 — digest sections and default window.

### S6. `agentwatch cost` — make the captured usage answerable · v0.1.0 · (new)

**Why.** A5 captures tokens and model version; M6 computes dollars from a versioned pricing table. Maya's (P1)
literal question — quoted in `20-usage-accounting.md:12` — is *"what did that run cost?"*, and answering it
currently needs the analytics service, Postgres, and the UI running. PRD 01 names "token-cost explosion" as an
agent-specific failure traditional observability misses. The data is in the local store; the answer should be
one command with zero services.

**Behavior.**
```sh
agentwatch cost [--by session|project|model|tool|day] [--since 30d] [--json]
```
Deterministic rollup over stored `session-usage` records against the versioned pricing table, with the table
version stamped in output; unknown models reported as `tokens only, price unknown` rather than estimated.
`--by tool` attributes cost to the tool-use pattern that caused it.

**Data & schema impact.** Derived read over A5 + M6 pricing; no record change.

**Security & privacy.** Derived read; no enforcement, no budget blocking (that is agentpolicy).

**Edge cases.** Missing price → `tokens only, price unknown`, never interpolated. Mixed currencies → single
documented currency. Sessions with no usage record → excluded with a note.

**Dependencies.** A5 (shipped), M6 pricing table, H6 shared read-command options.

**Testing.** A fixture session rolls up to the hand-derived dollar value; an unknown model is reported
tokens-only; the pricing-table version is present in `--json`.

**Risks & mitigations.** Stale pricing presented as fact → stamp table version + as-of date; never
interpolate.

**Decision.** D-32.9 — pricing-table versioning and the `--by tool` attribution rule.
