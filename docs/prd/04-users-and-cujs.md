# PRD 04 — Users and Critical User Journeys

**BLUF:** The primary users are platform and security engineers who need **proof of what agents did**
before they will trust any enforcement. The v0.1.0 journey is deliberately small: install, record, replay,
export — on Claude Code, in ≤15 minutes, with zero agent-side code changes. The v0.1.0 additions extend it to
**evidence hand-off, trust proof, cost, SDK union, erasure, MCP drift, and approval provenance** (CUJ-8–14,
PRDs 31–39). The **v0.2.0 additions** extend it further to **standards-compliant audit export, cross-agent/host
attribution, live watching, continuous compliance, detector evaluation, and cross-org delegation** (CUJ-15–20,
PRDs 40–48). The **v0.2.0-expanded additions** (PRD 49–59) add **authorization & oversight provenance, enterprise
deployability, harness-native telemetry, capability supply chain, code provenance, a zero-Docker local console,
agent-facing interfaces, policy-from-history, governance/retention integrity, and investigation depth** (CUJ-21–34).

**Status:** v0.1.0 + v0.2.0 additions (2026-10-05); **v0.2.0-expanded** (2026-10-05, PRD 49–59) · **Parent:** agentsec-ecosystem #209 · **v0.2.0:** PRD 40

## Users

| Persona | Who | What they need from agentwatch |
|---|---|---|
| **P1 Maya — platform engineer** | Runs agent tooling for a team | A record that exports to a backend the team already owns; near-zero setup |
| **P2 Ravi — security engineer** | Owned the incident postmortem | A defensible, tamper-evident audit trail; the security-event schema |
| **P4 Sam — solo developer** | One person, many agents | A local audit trail with no cloud dependency |
| **P5 Alex — embedder** (secondary) | Builds agents into a product | An SDK/OTLP path to instrument their framework and emit the schema |
| **P6 Dana — engineering lead / FinOps** | Owns team velocity and AI spend | Cost vs. what shipped, adoption by mode/harness, "is this working?" — without reading JSON (CUJ-29) |
| **P7 Imran — endpoint / IT admin** | Rolls tooling to hundreds of laptops via MDM/managed settings | A recorder that survives managed policy, is verifiably "on" fleet-wide, and doesn't slow developers (CUJ-25, CUJ-31) |

## Users this is *not* for

- Simple chatbots with no tools, state, or long-running behavior.
- Anyone who only wants prompt/completion analytics (that's an LLM observability tool).
- Anyone who wants a dashboard *product* from us — we ship data, not a dashboard.

## User problems

1. **Agent failures are hard to explain.** Even when a run fails or gets expensive, the behavior path is
   unclear.
2. **Generic telemetry is too shallow.** Normal logs/metrics don't capture tool calls, MCP servers,
   replays, or security events.
3. **Nothing is provable after the fact.** Compliance and incident review both fail on "no record".
4. **Signals are fragmented.** Security events, cost, and behavior live in different systems.

## Critical user journeys (v0.1.0)

### CUJ-1 — Install and record (the core journey)
1. Fresh machine with Claude Code. Run `npx @agentsec-ecosystem/cli init`.
2. The CLI installs the Claude Code hooks + local daemon, monitor-only by default.
3. Use Claude Code normally.
4. **Success:** the first tool call is recorded in ≤15 minutes, with **zero changes to the agent or its
   code**, and no secret/PII in the stored record.

### CUJ-2 — Replay a session
1. `agentsec sessions` lists recorded sessions.
2. `agentsec replay <session-id>` reconstructs the ordered action timeline.
3. **Success:** the replay matches the raw transcript in an automated test.

### CUJ-3 — Export to a backend you own
1. Point agentwatch at an OTLP endpoint.
2. Records flow to a standard OTel backend (e.g. Phoenix) unmodified.
3. **Success:** data loads into ≥2 common backends without transformation.

### CUJ-4 — Consume/emit a security event
1. A policy denies a tool call (agentpolicy) or a secret is detected.
2. agentwatch emits the named event (`denied`, `policy-fired`, `secret-detected`, …) in the schema.
3. **Success:** the schema is published, and ≥1 other ecosystem tool emits it.

### CUJ-8 — Investigate an incident and hand over evidence (P2 Ravi) · **the flagship journey**
1. `agentwatch search --tool Bash --outcome error --since 2d` finds the suspect session.
2. `agentwatch impact <id>` (S3) shows the footprint: files, commands, hosts, git refs.
3. `agentwatch replay <id>` / `view` walks the sequence; `explain` narrates it.
4. `agentwatch coverage --session <id>` (S2) confirms nothing was missed.
5. `agentwatch evidence <id> --out incident-4471.zip` (S1).
6. **Success:** a third party verifies the bundle offline, on a different machine, without installing
   agentwatch, and the three verdicts (intact / complete / leak-free) are unambiguous.

*Why it matters:* this is the product's value proposition executed end to end; today it stops at step 3 and
J3 (the investigation cookbook) has nowhere to go next.

### CUJ-9 — Prove the recorder deserves trust (P1/P2)
1. `agentwatch doctor` — environment and install are sane.
2. `agentwatch verify-store` — the chain is intact.
3. `agentwatch verify-privacy` — zero leaks under *my* config and *my* store.
4. `agentwatch coverage` (S2) — capture rate, with every gap classified.
5. **Success:** four commands produce one shareable trust report; `gap:unexplained` is zero. A security
   engineer can run this *before* adopting, and an auditor *during* review.

### CUJ-10 — Answer "what did our agents cost last week?" (P1 Maya)
1. `agentwatch cost --by project --since 7d` (S6), then `--by tool` to find the driver.
2. `agentwatch diff` the expensive session against a cheap one.
3. **Success:** answered in one command with no services running, with the pricing-table version stamped in the
   output.

### CUJ-11 — Instrument my own agent and see it beside the harness records (P5 Alex)
1. Add `@trace_agent` to a framework agent (parity SDK).
2. Point it at the local collector; `agentwatch sessions` lists the run with `source: sdk` (S11).
3. The same operator UI shows harness and SDK activity side by side, integrity distinction visible.
4. **Success:** P5 finally has a journey, and the "one install, one format" claim is demonstrable rather than
   aspirational.

### CUJ-12 — Erase on request and prove it (P1/P2)
1. `agentwatch purge <id> --reason "subject request" --yes` (shipped).
2. `agentwatch verify-store` — chain still green, tombstones and the purge marker enumerated.
3. `agentwatch evidence <id>` — a bundle that *proves the erasure happened* without resurrecting the content.
4. **Success:** a defensible erasure record — the GDPR/DSAR shape, and the thing "tombstone, never hard
   delete" (D-K) was built for but never surfaced as a journey.

### CUJ-13 — Notice an MCP server changed under me (P2)
1. `agentwatch inventory --diff --server payments` (S4).
2. A `tool-surface-changed` event names added/removed tools with first/last-seen timestamps.
3. **Success:** a rug-pull is *provable after the fact* — the exact claim `01-why.md:27` makes.

### CUJ-14 — Answer "did a human approve that?" (P2 Ravi)
1. `agentwatch search --approval user --since 30d` (S14) lists every call a person authorized.
2. `agentwatch blame <path>` (S18) shows who touched the file that broke, and under what approval.
3. `agentwatch tree <id>` (S17) shows which subagent did it, since subagents are where responsibility
   currently vanishes.
4. **Success:** for any destructive action in the record, the answer is `user`, `auto`, `not-required`, or an
   honest `unknown` — never an inference.

*Why it matters:* the record answers "what happened" and cannot yet answer "who allowed it," which is the
question that decides whether an incident is a bug or a process failure.

## Critical user journeys (v0.2.0 additions — PRD 40–48)

These extend the v0.1.0 set. Same format, same standing guarantees. Owners: the PRD in parentheses.

### CUJ-15 — "My auditor accepts my agent logs" (P2) · PRD 41 (AAT)
1. `agentwatch export-session <id> --format aat --out session-4471.aat.json`.
2. A third-party AAT consumer (not agentwatch) validates the records and the chain.
3. **Success:** the artifact is accepted by a tool that has never heard of agentwatch; unmapped fields are explicit,
   never invented.

*Why:* EU AI Act Art. 12(2) requires logs conforming to "recognized standards." Evidence in a vendor format argues;
evidence in the IETF format complies.

### CUJ-16 — "Follow one action across agents and hosts" (P2) · PRD 41 (TRACE) + PRD 44 (IDN)
1. An incident spans a Claude Code session, an MCP hop, and a PydanticAI backend agent on another host (opt-in fleet).
2. `agentwatch trace <trace-id>` reconstructs the causal chain across processes and hosts.
3. Each hop shows identity, delegation (on whose behalf), and approval provenance.
4. **Success:** "which agent, on which machine, under whose approval, on whose behalf" is complete or an honest
   `unknown` — never an inference.

*Why:* the multi-agent attribution problem NIST/CSA call structurally unsolved.

### CUJ-17 — "Watch a live agent" (P1) · PRD 42 (STR)
1. An operator opens the timeline while an agent works (or `agentwatch tail -f`).
2. Records stream in; anomalies land in the live inbox.
3. **Success:** p99 hook → view ≤ 1 s; a dropped view reconciles via back-fill with every gap classified; zero store
   loss on consumer crash.

*Why:* batch polling (~30 s) is the most visible released limitation; SOC consumers expect streamable telemetry.

### CUJ-18 — "Prove compliance continuously" (P2) · PRD 44 (CMP)
1. `agentwatch compliance report --framework iso-42001 --period Q3-2026 --out audit/`.
2. The report lists each control: verdict, the evidence command that regenerates it, bundle refs, retention +
   chain/signature status.
3. **Success:** runs offline/air-gapped; every row cites a third-party-verifiable artifact; an auditor reproduces any
   row from the cited command alone.

*Why:* "one-click compliance reports" is category table stakes; buyers procure for EU AI Act Art. 12 now.

### CUJ-19 — "Does this detector actually fire for us?" (P1/P2) · PRD 43 (DET/COR)
1. An evaluator reads published per-detector precision/recall in the detector catalog.
2. They run `agentwatch detectors eval` against their own local, redacted corpus.
3. **Success:** their numbers and ours are comparable; the harness is deterministic and offline; opt-in detector
   telemetry shows fired/suppressed/false-positive counts on live traffic.

*Why:* "43 detectors" with 28 silent is a claims-ledger liability; published effectiveness is the honest answer.

### CUJ-20 — "Who did my agent just delegate to?" (P2/P5) · PRD 45 (A2A) + PRD 44 (IDN)
1. An agent hands a task to a remote agent at another organization via A2A.
2. The record shows the signed agent card, the security scheme, the task lifecycle, and the local causal chain.
3. **Success:** cross-org delegation is provable after the fact (signed identity, scheme, outcomes); unverified cards
   recorded as unverified — no invented attribution.

*Why:* A2A (150+ orgs, v1.0, hosted beside MCP) makes cross-org delegation routine; NIST identifies it as where
non-repudiation breaks down.

## Critical user journeys (v0.2.0-expanded — PRD 49–59)

These continue CUJ-15–20. Format unchanged.

### CUJ-21 — "Was a human actually in the loop?" (P2, P6) · PRD 49 + PRD 51
1. `agentwatch replay <id>` shows each call's authorization source and permission mode at that moment.
2. `agentwatch oversight --since 30d --project infra` shows authorization mix and destructive-calls × source.
3. `agentwatch evidence <id>` bundles it; a third-party verifier shows authorization/mode without installing agentwatch.
**Success:** every destructive call is human/rule/classifier/hook/bypass/not-required or an honest `unknown` — never
`user` when a classifier approved; cross-tab produced offline in <5 s on 100k records; ≥95% non-`unknown` with native
telemetry (FT-APV-1/2, FT-CCO-1).

### CUJ-22 — "Which commit did the agent write, and under what oversight?" (P2, P6, reviewers) · PRD 53
1. `agentwatch provenance <commit|PR>` → sessions, per-file attribution + confidence, authorization, cost, coverage.
2. `export-session <id> --format agent-trace`; optional git-ai notes cross-validation.
**Success:** commit→session <2 s; no recorded activity says so (not "human"); mixed ranges correct; export contains no code
content (FT-PRV-1).

### CUJ-23 — "Did a skill, plugin or rules file change under me?" (P2) · PRD 52
1. `inventory --capabilities --diff --since 7d` → added/changed with origin + digest.
2. `capability-changed` event ("content changed, version unchanged") in sink + `tail`.
3. `search --capability <name>`; `impact <id>` lists loaded capabilities.
**Success:** Plugin4Shell-shape fixture detected; digests never content; <1 s when daemon live (FT-CAP-1, FT-MEM-1).

### CUJ-24 — "Show me my agents in a browser — in 60 seconds, no Docker" (P4, P1) · PRD 54
1. `agentwatch init`; use Claude Code; `agentwatch ui` → browser; sessions → timeline; export evidence.
**Success:** ≤15 min fresh machine, ≤60 s from `ui`; UI=CLI parity; loopback/read-only/no-egress (FT-LUI-1).

### CUJ-25 — "Roll out to 300 laptops under managed settings — and know it's on" (P7, P1) · PRD 50
1. Deploy as managed hook/org plugin via MDM; `doctor` → "hooks effective: yes (managed)"; fleet shows recording status.
**Success:** `doctor` never says "installed" when blocked; 100% sessions attested or `attestation:absent`; hook overhead in
budget on 3 OSes (FT-DEP-1/2/3).

### CUJ-26 — "Let an agent query the record safely" (P5, P4, P2) · PRD 55
1. `init --mcp-serve`; ask a coding agent "what changed in infra/ last night?"; it cites record IDs; query recorded.
**Success:** no write tool; untrusted labeling; injection fuzz holds; byte-identical removal (FT-AGI-1).

### CUJ-27 — "Turn 30 days of history into a tighter policy" (P2, P1) · PRD 55
1. `suggest-policy --since 30d --target claude-settings --out proposed.json`.
2. `what-if proposed.json --since 30d` → prompts avoided, would-be denials.
**Success:** no write outside `--out`; dangerous-broad lint; destructive never allow-by-default (FT-POL-1).

### CUJ-28 — "Instrument my non-LangGraph agent in two lines" (P5) · PRD 51
1. `instrument()` in ADK/Strands/OpenAI Agents/Claude Agent SDK; run; sessions carry identity/tools/cost/`source`.
**Success:** ≤2 lines per framework, CI-executed; no silent partial instrumentation; flush-on-exit (FT-FWK-1).

### CUJ-29 — "What did our AI work cost versus what stuck?" (P6) · PRD 58 (+PRD 51/53)
1. `outcomes --since 30d --by project`; `cost --by project --per retained-change`; `digest`.
**Success:** numerator/denominator + derivation version; deterministic offline; answers one command (CUJ-29).

### CUJ-30 — "My CI/cloud agent ran unattended — give me the evidence" (P1, P2) · PRD 58
1. CI records a run → sealed segment artifact; `import-segment` verifies + labels `source: runner`.
**Success:** tampered segment fails; imported records distinguished; no egress; trace joins when `traceparent` present
(FT-RUN-1).

### CUJ-31 — "Roll out recording to employees — lawfully and transparently" (P7, P2, DPO) · PRD 56
1. `governance notice` from effective config; DPIA starter; least-privileged fleet profile; self-visible access log.
**Success:** every notice statement maps to a config key or guarantee; cross-role reads return nothing + are logged;
identity resolution recorded (FT-ACC-1).

### CUJ-32 — "Legal says: preserve everything for this case" (P2, counsel) · PRD 56
1. `hold add --scope … --ref CASE-123`; `retention apply --dry-run` shows skips; `purge` refuses; report lists hold.
**Success:** held records survive retention/purge/rebuild; override requires reason and is conspicuous (FT-HLD-1).

### CUJ-33 — "It worked last week — what changed?" (P1, P6) · PRD 57
1. `diff <good> <bad>` shows environment delta above behavior delta; `drift` annotates; `sessions --group-by-env`.
**Success:** names model/harness/capabilities/mode/config changes or `unknown`; "coincides with" wording (FT-ENV-1).

### CUJ-34 — "Package this incident: many sessions, many people, one case" (P2) · PRD 57
1. `case create INC-4471`; add sessions; `case show` merged timeline; `case export` bundle + report.
**Success:** ordering rules + gaps classified; manifest lists per-session verdicts; no registry egress (FT-IR-1).

**CUJ-8 extension — "Verify with nothing installed" (auditor) · PRD 57 (VFY-1):** open a static page, drop the bundle,
read verdicts. **Success:** zero network; verdicts equal CLI; tampered bundle names the first broken link (FT-VFY-1).

## Later journeys (not v0.1.0)

- **CUJ-5 — Inventory:** "what agents/MCP servers exist on this machine?" (R9).
- **CUJ-6 — Compare versions:** behavior changed between agent/prompt/model versions (absorbed from
  AgentObservatory).
- **CUJ-7 — Drift:** behavioral drift relative to a trailing baseline (absorbed from AgentWatch; alerting
  lives in agentpolicy).

## Success criteria for v0.1.0 users

CUJ-1 through CUJ-4 and the v0.1.0 additions CUJ-8–14 pass on a clean machine, and a security engineer can
answer "what did that agent do?" in <5 minutes from a standard backend — and can hand a third party an evidence
bundle they can verify offline (CUJ-8).

## Success criteria for v0.2.0 users

CUJ-15 through CUJ-20 pass on a clean machine (per their owning PRDs), and: an auditor with no agentwatch
knowledge accepts an AAT export (CUJ-15); a cross-agent incident is attributed end-to-end in one command
(CUJ-16); a live session is watched with p99 ≤ 1 s and no silent gaps (CUJ-17); a compliance report runs
offline and every row regenerates (CUJ-18); a published detector number is reproduced locally (CUJ-19); a
cross-org delegation is provable from signed cards (CUJ-20).

**v0.2.0-expanded (CUJ-21–34):** every destructive call carries a truthful authorization source and permission mode
(CUJ-21); a commit resolves to the session that wrote it, or says so (CUJ-22); a capability content-swap is detected
(CUJ-23); a Claude Code/Cursor user sees a browser view of their own record in ≤60 s with no Docker (CUJ-24); a managed
fleet is verifiably recording (CUJ-25); an agent can query the record read-only and safely (CUJ-26); history yields an
advisory policy and a what-if (CUJ-27); the four target frameworks instrument in ≤2 lines (CUJ-28); cost-vs-outcome is
answerable in one command (CUJ-29); an unattended runner produces a verifiable segment (CUJ-30); a monitoring rollout is
lawful and transparent (CUJ-31); a legal hold survives retention and purge (CUJ-32); "what changed?" is answered
environmentally (CUJ-33); an incident packages across sessions (CUJ-34); and a bundle verifies with nothing installed
(CUJ-8 ext).
