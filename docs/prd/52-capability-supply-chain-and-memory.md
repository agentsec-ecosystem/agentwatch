# PRD 52 — Capability Supply Chain & Memory

**BLUF:** Bring the 2026 agent supply chain into the record: **skills, plugins, hooks, subagent definitions, slash
commands, instruction/rules files, MCP servers and persistent memory** are inventoried with **content digests**, drift
is surfaced as a `capability-changed` security event, and each action can be attributed to the capabilities loaded
before it. The rug-pull threat the corpus already tracks for MCP tools (CUJ-13) now covers the surfaces attackers
actually use: Plugin4Shell, ClawHavoc, ToxicSkills, SKILL.md poisoning.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 25, PRD 36 (S4), PRD 43 (DET-7), PRD 50 (DEP-2) · **Extends:** R9 inventory, S4 tool-surface drift,
S9 Agent BOM, `CLAUDE.md` fingerprint · **Adds/extends:** CUJ-23 (extends CUJ-13)

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in
> (R6); no new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **record and diff capabilities; never scan or judge them.** Detection verdicts belong to vendor scanners
and agentdrill; enforcement belongs to agentpolicy.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| CAP-1 | Capability inventory with content digests + origin scope | Skills/plugins are the new npm; 36.8% flawed, 1,184 malicious in one marketplace | 23 |
| CAP-2 | Capability drift + `capability-changed` event | Rug-pull via background auto-update; digest≠version | 23 |
| CAP-3 | `capability-loaded` attribution | Skill-borne attacks steer later calls; need "what was loaded" | 23 |
| MEM-1 | Memory-store inventory, drift, writer attribution | Persistent memory is a cross-session poisoning path (ASI06) | 23 |

## CAP-1 — Capability inventory · (new)

**Why.** The record's reach must match the attack surface: Snyk flagged 1,467/3,984 skills (13.4% critical);
ClawHavoc confirmed 1,184 malicious skills; Plugin4Shell (2026-09-17) swaps a pinned plugin for a malicious one,
zero-click, across four coding agents; OWASP lists Agentic Supply Chain (ASI04) and a dedicated Agentic Skills Top 10.
Inventory today = agents + MCP servers + one `CLAUDE.md` digest.

**Behavior.** `inventory` and `bom` enumerate, per machine/project/session: skills, plugins (source marketplace +
version), hooks (including non-agentwatch), subagents/commands, instruction/rules files (`CLAUDE.md`, `AGENTS.md`, rules
dirs), MCP servers, **and memory stores** — each with a **content digest**, first/last-seen, and origin scope
(managed/user/project/plugin).

**Acceptance.**
- [ ] One command lists active capabilities with scope + digest; `bom --format cyclonedx` includes them as components.
- [ ] Digest is of content, not of the declared pin (the Plugin4Shell shape).
- [ ] Per-harness coverage (Claude Code, Cursor, Codex, Gemini) declared honestly; unsupported = named gap.
- [ ] Capability file content is never stored (digests/names/sizes/origin only; privacy-tested).

**Data & schema impact.** New inventory components; no record-schema change.
**Security & privacy.** No content storage; digests only; read-only.
**Dependencies.** PRD 47 (testkit), adapter research.
**Risks & mitigations.** Harness config formats differ → per-harness fixtures + drift. **Decision.** ADR-0032.

## CAP-2 — Capability drift · (new)

**Why.** Background auto-update is the default in Claude Code and Codex; the benign→malicious swap is the highest-leverage
supply-chain attack and CUJ-13's "provable after the fact" promise covers only MCP.

**Behavior.** Generalize S4 snapshot/diff to all capability types. Content-digest changes *without* a version change, a
new capability from an unseen origin, or a new hook emit `capability-changed` (schema-governed; OCSF/CloudEvents mapped).

**Acceptance.**
- [ ] `inventory --diff --since 7d` lists added/removed/changed with first/last-seen + origin.
- [ ] "content changed, version unchanged" is a distinct, highlighted class (FT-CAP-1).
- [ ] New non-agentwatch hook appearing in project settings is surfaced (ties to hook persistence).
- [ ] No verdict language ("changed", not "malicious"); event appears in SIEM sinks + compliance report.

**Dependencies.** CAP-1, schema stewardship, PRD 50 (attestation includes managed-only/strict flags).
**Risks & mitigations.** False alarms on legitimate updates → version-aware diff; declared.
**Decision.** ADR-0032.

## CAP-3 — Load attribution · (new)

**Why.** Skill-borne attacks work by being loaded into context then steering later calls; investigators need "which
capability was in play when this call happened". `tree` attributes subagents only.

**Behavior.** Where the harness exposes loads, record a metadata-only `capability-loaded` step (name, origin, digest) so
`replay`/`impact`/`blame`/`flow`/`evidence`/`search` can show it as context.

**Acceptance.**
- [ ] `replay <id>` shows loads inline; `search --capability <name>` returns sessions/calls after a load (FT-MEM-1 analog).
- [ ] `impact <id>` lists capabilities loaded during the session beside files/hosts.
- [ ] Per-harness exposure matrix published, CI-checked; wording is "followed the load of", never "caused".

**Dependencies.** CAP-1, PRD 50.

## MEM-1 — Memory as a capability · (new)

**Why.** Claude Code now keeps persistent auto-memory loaded into future sessions; memory poisoning is OWASP ASI06. DET-7
records memory observations, but the memory *store* isn't inventoried, so a poisoned file changed between sessions isn't diffed.

**Behavior.** Treat memory stores as capabilities: digest, size, last-changed, and the session that wrote each change.
Content is never stored. `replay` marks memory loads/writes; `search --memory` returns sessions following a memory change.

**Acceptance.**
- [ ] Memory change not attributable to any recorded session (edited outside the agent) is flagged as such.
- [ ] Per-harness exposure matrix (exposed/partial/none) published; unsupported is a declared gap.

**Dependencies.** CAP-1/3, DET-7, PRD 51 (native telemetry where available). **Decision.** ADR-0043.

## Not goals
Scanning skill/memory content for maliciousness; blocking loads; executing or rendering capability content.

## Sources
CSA "Agent Context Poisoning: SKILL.md…" (2026-05-06); CSA "Poisoned Skills" (2026-06-24); arXiv 2605.14460 (SCH);
Air "Plugin4Shell" (2026-09-17); OWASP ASI04 / Agentic Skills Top 10; Claude Code settings-reference (autoMemoryEnabled).
Local analysis files 03, 07, 10.
