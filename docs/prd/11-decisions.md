# PRD 11 — Decisions (accepted)

**BLUF:** All review decisions were **accepted on 2026-10-02**. This page records the choices. Two items
(DD-14, DD-15) have an accepted direction but are finalized during the build.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## A. Design decisions — accepted

| ID | Decision |
|---|---|
| DD-01 | **Python core** for true parity; `npx @agentsec-ecosystem/cli` is a thin launcher; CLI on PyPI |
| DD-02 | Record format = OTel GenAI spans + versioned security-event schema |
| DD-03 | Local-first storage; export opt-in via OTLP |
| DD-04 | Adapter boundary as an explicit contract; Claude Code hooks first |
| DD-05 | Contribute schema upstream to OTel GenAI; don't fork; repo-local copy until adopted |
| DD-06 | Redaction at normalization time, before storage |
| DD-07 | Storage hash-chained for tamper evidence |

## B. Product & scope — accepted

| # | Decision |
|---|---|
| B1 | **v0.1.0 = Claude Code only** (monitor-only); Cursor lands in v0.1.x |
| B2 | **Parity gate at v1.0** — full shipped-feature parity delivered + tested |
| B3 | **Superset positioning** — agentwatch is record **+ analyze + explore + UI** (not telemetry-only) |
| B4 | **PyPI/npm name `agentwatch`**; `@agentsec-ecosystem/cli` stays the npx launcher |
| B5 | **Preserve** `@trace_agent`/`TracedGraph` + read-API shapes; ship a compat shim + migration note |

## C. Technical — accepted

| # | Decision |
|---|---|
| C1 | v0.1.0 store = append-only **JSONL + hash chain**; Postgres for analytics in v0.2.0 |
| C2 | Hash-chain key: **detect-only** for v0.1.0 |
| C3 | Event naming/versioning → **DD-14** (propose into OTel before locking schema v1) |
| C4 | **Gate OTLP export** on a passing redaction self-test |
| C5 | Cursor recording → **DD-15** (native first, proxy only where needed) |
| C6 | Schema stewardship: **propose upstream from day one**, keep repo-local copy (DD-05) |
| C7 | "Kept it on" measured **locally**; user shares voluntarily — no silent telemetry |

## D. Governance & legal — accepted

| # | Decision |
|---|---|
| D1 | **Apache-2.0**, with `THIRD_PARTY_NOTICES` crediting the MIT-licensed `agent-exec-trace` |
| D2 | **Reserve `agentwatch`** (PyPI + npm) before publishing |

## Status

- **Blocking v0.1.0 build:** resolved (DD-02..DD-09, B1, C1, C4, C7).
- **Finalize during build:** DD-14 (event naming), DD-15 (Cursor recording).
- **Before first release:** D1 (notices), D2 (name reservation).

## E. Additions decisions (proposed, PRD 19–30)

Recommendations pending a ruling; each is referenced as `D-19.x` in the PRD that needs it.

| ID | Decision |
|---|---|
| D-A | Boundary/external/event records reuse the existing record convention vs. a new envelope type — **reuse `tool.name`** |
| D-B | Emitter for harness-native denials — **`claude-code`; agentpolicy stays canonical** |
| D-C | Async hooks by default — **yes, with an out-of-order Pre/Post test** |
| D-D | Store rotation vs single file — **single file for v0.1.0** |
| D-E | Where cost is computed — **SDK records tokens+model; analytics owns pricing** |
| D-F | Quarantine shape — **same chained envelope, owner-only, beside the store** |
| D-G | Subagent trace identity — **share session trace; spans distinguish** |
| D-H | CLAUDE.md hash as `prompt_version` — **allow; hash-only, documented** |
| D-I | Tool responses — **extend schema 0.1.0 now, pre-release** |
| D-J | Spool semantics — **size-bounded, drained in order, records marked recovered** |
| D-K | Purge — **tombstone, never hard delete** (PRD 15 invariant) |
| D-L | `view` TUI — **stdlib curses only; any dependency needs an explicit ruling** |
| D-M | Import — **explicit opt-in command, never automatic; never scan without consent** |
| D-N | Durability default — **keep per-record fsync; offer documented modes** |
| D-O | LLM assistant — **local model or explicit endpoint only; never silent egress; deterministic summary always printed** |
| D-P | MCP proxy — **opt-in install with explicit interposition consent; async forwarding; uninstall restores config** |
| D-Q | Ingestion scope — **records + security events first; not a general OTel backend** |
| D-R | Conformance runner — **blocking CI gate for every adapter, community included** |
