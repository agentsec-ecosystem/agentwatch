# PRD 11 — Open Decisions (Review Tracker)

**BLUF:** Everything that still needs owner sign-off before the v0.1.0 build, each with a recommendation.
**DD-01 is accepted.** Everything else below is open.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## A. Design decisions still `proposed`

From [design/design-decisions.md](../design/design-decisions.md). Recommendation: accept all six.

| ID | Decision | Recommendation |
|---|---|---|
| DD-02 | Record format = OTel GenAI spans + versioned security-event schema | Accept |
| DD-03 | Local-first storage; export opt-in via OTLP | Accept |
| DD-04 | Adapter boundary as an explicit contract; Claude Code hooks first | Accept |
| DD-05 | Contribute schema improvements upstream to OTel GenAI; do not fork | Accept *(see C6)* |
| DD-06 | Redaction at normalization time, before storage | Accept |
| DD-07 | Storage hash-chained for tamper evidence | Accept |

## B. Product & scope

| # | Decision | Options | Recommendation |
|---|---|---|---|
| B1 | **v0.1.0 harness scope** (ecosystem asks ≥2 Tier-1; meta-MVP says one) | Claude Code only, or +Cursor at v0.1.0 | **Claude Code only**; Cursor in v0.1.x |
| B2 | **Parity gate** | v1.0 = full shipped-feature parity, or an earlier version | **v1.0** — parity-complete and tested |
| B3 | **Superset positioning** | telemetry-only vs record + analyze + explore + UI | **Superset** (parity forces it) |
| B4 | **PyPI package name** | new `agentwatch` (free) vs continue `agent-exec-trace` | **`agentwatch`** (free on PyPI + npm); keep `@agentsec-ecosystem/cli` as the npx launcher |
| B5 | **API compatibility** | preserve `@trace_agent`/`TracedGraph` + read-API shape, or documented migration | **Preserve** + a compat shim; publish a migration note |

## C. Technical open questions

| # | Question | Recommendation |
|---|---|---|
| C1 | v0.1.0 store: embedded (SQLite) vs append-only JSONL; reuse Postgres for analytics later | JSONL with a hash chain for v0.1.0; Postgres for analytics in v0.2.0 |
| C2 | Hash-chain key management: detect-only vs a local key | **Detect-only** for v0.1.0 (simplest, still tamper-evident) |
| C3 | Security-event naming/versioning: OTel events vs custom attributes | Decide with the schema v1; propose into OTel before locking |
| C4 | Export gating: block OTLP export until a redaction self-test passes? | **Yes** — gate export on a passing redaction self-test |
| C5 | Cursor recording: native hooks vs proxy interposition, per event class | Prototype native first; proxy-interpose only the classes native can't capture |
| C6 | Schema stewardship: solo steward vs propose into OTel GenAI (DD-05) | Propose upstream from day one; keep a repo-local copy until adopted |
| C7 | Success measurement of "kept it on": opt-in anonymous heartbeat vs local-only status | **Local-only** status the user shares voluntarily (no silent telemetry) |

## D. Governance & legal

| # | Decision | Recommendation |
|---|---|---|
| D1 | Absorbed `agent-exec-trace` code is **MIT**; new repo is **Apache-2.0**. Re-license absorbed code and attribute. | Confirm. MIT → Apache-2.0 redistribution is permitted; add `THIRD_PARTY_NOTICES` crediting the original. |
| D2 | Reserve names: `agentwatch` (PyPI + npm free), `@agentsec-ecosystem/cli` | Reserve `agentwatch` before publishing |

## Path to "ready to build"

1. Accept/deny **A (DD-02..DD-07)** and **B1–B5**.
2. Resolve **C1, C4, C7** (block v0.1.0); **C2, C3, C5, C6** can be decided during the build.
3. Confirm **D1–D2** before the first release.
