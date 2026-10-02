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
