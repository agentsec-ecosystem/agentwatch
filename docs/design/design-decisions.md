# agentwatch — Design Decisions

Centralized decision log. Referenced as `DD-NN`. **All decisions below were accepted on 2026-10-02.**

| ID | Decision | Status | Rationale |
|---|---|---|---|
| DD-01 | **Core runtime:** Python core (SDK + analytics service + API) for true shipped-feature parity; `npx @agentsec-ecosystem/cli` is a thin launcher; CLI also published on PyPI | accepted | Parity with the shipped `agent-exec-trace` Python SDK/services; preserves instrumentation/read-API contracts |
| DD-02 | Record format = OTel GenAI spans (`execute_tool`) + a versioned security-event schema | accepted | Standards alignment; portability; schema is the differentiator |
| DD-03 | Local-first storage; export opt-in via OTLP | accepted | Privacy by default (R6) |
| DD-04 | Adapter boundary as an explicit contract; Claude Code hooks are the first implementation | accepted | Harness-agnostic by construction (R3) |
| DD-05 | Contribute schema improvements upstream to OTel GenAI; do not fork; keep a repo-local copy until adopted | accepted | Adoption > control |
| DD-06 | Redaction happens at normalization time, before storage | accepted | Never persist secrets (R7) |
| DD-07 | Storage hash-chained for tamper evidence | accepted | Forensic trust (R11) |
| DD-08 | **v0.1.0 store:** append-only JSONL + hash chain; Postgres used for analytics in v0.2.0 | accepted | Simple, local-first, tamper-evident; matches the shipped analytics stack when it lands |
| DD-09 | **Gate OTLP export** on a passing redaction self-test | accepted | Never export unredacted data (R7) |
| DD-10 | **"Kept it on" measured locally**; the user shares it voluntarily — no silent telemetry | accepted | Privacy baseline (PRD 06) |
| DD-11 | **Package names:** `agentwatch` (PyPI + npm); `@agentsec-ecosystem/cli` as the npx launcher | accepted | `agentwatch` is free on both registries |
| DD-12 | **Preserve shipped instrumentation** (`@trace_agent` / `TracedGraph`) and read-API shapes; ship a compat shim + migration note | accepted | Do not break existing agent-exec-trace users (PRD 10 §D) |
| DD-13 | **License:** Apache-2.0, with `THIRD_PARTY_NOTICES` crediting the MIT-licensed `agent-exec-trace` | accepted | MIT → Apache-2.0 redistribution is permitted; attribution required |

## Deferred (direction accepted, finalize during the build)

| ID | Decision | Direction |
|---|---|---|
| DD-14 | Security-event naming/versioning: OTel events vs custom attributes | Propose into OTel GenAI before locking the schema v1 |
| DD-15 | Cursor recording: native hooks vs proxy interposition, per event class | Prototype native first; proxy-interpose only the classes native cannot capture |

## Template

```
### DD-NN — Title
- **Status:** proposed | accepted | superseded
- **Context:**
- **Decision:**
- **Consequences:**
```
