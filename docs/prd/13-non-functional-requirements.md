# PRD 13 — Non-Functional Requirements

**BLUF:** The NFRs that make agentwatch safe to leave on: bounded overhead, bounded storage, local-only
privacy, fail-closed behavior, and portability across macOS/Linux.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

| ID | NFR | Target | Notes |
|---|---|---|---|
| NFR-1 | Per-step instrumentation overhead | **≤5 ms/step** | Parity with the shipped AgentWatch figure |
| NFR-2 | Ingestion latency (event → stored) | ≤30 s batch (v0.1.0); lower later | The shipped project was batch-polling (~30 s) |
| NFR-3 | Storage growth | Bounded; 30-day retention | R11; caps by size/time |
| NFR-4 | First-run setup | **≤15 min**, zero code changes | R2 |
| NFR-5 | Footprint | Small daemon memory/disk; no heavy deps at v0.1.0 | DD-08 (JSONL) |
| NFR-6 | Portability | macOS + Linux | Windows considered later |
| NFR-7 | Scale | 10k+ traces/day per host (v0.2.0+ ingestion) | Configurable fetch/limits |
| NFR-8 | Reliability | **Fail-closed** on tamper; never silently stop recording | PRD 06 |
| NFR-9 | Privacy | No egress by default; redaction before storage; export gated | R6, R7, DD-06, DD-09 |
| NFR-10 | Accessibility | Operator UI meets basic a11y (keyboard, contrast, labels) | ui-accessibility.md |
| NFR-11 | Test coverage | **>90%** with quality gates (ruff zero, mypy strict) | UI/generated code excluded |
| NFR-12 | Observability (of agentwatch) | Its own health/recording status is visible | "couldn't read the run" lesson |

## Self-observability spec (NFR-12)

agentwatch exposes its **own** health so operators can tell "clean run" from "couldn't read the run"
(the AgentObservatory lesson). It never claims to be recording when it isn't.

### Health endpoint

`GET http://127.0.0.1:9100/healthz` (configurable, see [PRD 16](16-configuration.md)) returns:

| Field | Type | Meaning |
|---|---|---|
| `state` | enum | `recording` · `degraded` · `stopped` |
| `daemon` | object | `pid`, `uptime_s`, `version` |
| `store` | object | `path`, `records`, `size_mb`, `chain_ok` (bool), `last_append_at` |
| `export` | object | `enabled` (bool), `endpoint`, `last_success_at`, `last_error` |
| `redaction` | object | `mode`, `self_test_passing` (bool) |
| `hooks` | object | per-harness: `installed` (bool), `last_fire_at`, `errors` (count) |
| `gaps` | array | recent recording-gap events (F1/F2/F8 from [PRD 17](17-error-handling.md)) |

### States

- **`recording`** — daemon up, chain intact, hooks firing, no active gap.
- **`degraded`** — recording but something is wrong (export failing, self-test failing, hook errors > 0).
- **`stopped`** — fail-closed (F1/F3/F4/F7); the state says *why*.

### Signals (also emitted as OTel metrics on the same exporter, when enabled)

- `agentwatch.records.stored` (counter) · `agentwatch.gaps` (counter) · `agentwatch.export.errors` (counter)
- `agentwatch.chain.broken` (gauge, 0/1) · `agentwatch.self_test.passing` (gauge, 0/1)

### CLI

`agentwatch status` prints the health summary for humans; `agentwatch verify-store` checks the chain.

### Guarantee

`state=recording` is only reported when the chain is intact and hooks are firing. A silent stop is a bug,
not a state (NFR-8).

## Parity NFRs

The shipped project's quality bar is retained: ruff zero violations, mypy strict clean, tests green,
coverage >90%.
