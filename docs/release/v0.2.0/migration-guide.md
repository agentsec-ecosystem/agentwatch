# Migration Guide — v0.1.0 → v0.2.0

**BLUF:** Upgrading is **additive**. v0.2.0 adds surfaces (identity, MCP full surface, detectors, SIEM sinks,
compliance, retention profiles, signed checkpoints); it does not break the v0.1.0 instrumentation API, read-API
shapes, store format, or record contract. A v0.1.0 store upgrades in place — no rewrite, no export/import.

Status: **release-ready** (v0.2.0). See the [v0.1.0 migration guide](../v0.1.0/migration-guide.md) for the
`agent-exec-trace` → `agentwatch` rename that preceded this.

## What changes

| Area | v0.1.0 | v0.2.0 | Breaking? |
|---|---|---|---|
| Instrumentation SDK | `@trace_agent`, span helpers, `TracedGraph`, `AgentTracer.setup`, privacy modes | unchanged (source-compatible) | no |
| Import root | `agentwatch` (legacy `agent_exec_trace` shim) | unchanged; shim still works, **codemod** provided | no |
| Store | JSONL + hash chain, format `1` | format `1` unchanged; opens and verifies a v0.1.0 store in place | no |
| Record schema | `schema_version` `0.1.0` | accepts `0.1.0` **and** `0.2.0`; new optional fields | additive |
| Security events | `event_version` `0.1.0` | accepts `0.2.0`; adds `agent-delegation` | additive |
| Read API | `/runs`, `/fleet`, `/compare`, `/anomalies` | same shapes; **new** read-only endpoints (attribution, SIEM health, detector telemetry) | additive |
| CLI | core subcommands | new subcommands/flags (`mcp`, `compliance report`, `checkpoint rotate`, `retention apply --profile`, `search --identity`, …) | additive |
| Config | layered TOML/env | same keys; new `sinks`/`sampling` sections have defaults | additive |

## Record schema additions (read with honest defaults)

v0.2.0 adds optional fields on top of the v0.1.0 record; an old reader ignores them, and a v0.2.0 reader sees an
honest `None`/absent value on a v0.1.0 record:

- `record_phase` (`pre_execution` | `post_execution` | `unknown`) — AAT.
- `traceparent` — W3C Trace Context, for multi-host correlation.
- `agent_identity` dimension on `agent`: `workload_identity`, `credential_class`
  (`api-key` | `oauth` | `svid` | `ambient/shared`), `principal` (hashed by default), `delegation_chain`.

See [`schema/CHANGELOG.md`](../../../schema/CHANGELOG.md) and the
[record-format spec](../../reference/record-format-spec.md).

## Steps

1. **Upgrade the package:** `pip install -U agentsec-agentwatch`.
2. **Point your imports at `agentwatch`** (or keep the shim). Use the codemod:

   ```sh
   python scripts/codemod_agent_exec_trace.py path/to/src
   python scripts/codemod_agent_exec_trace.py --check path/to/src   # CI dry-run
   ```
3. **Leave the store alone.** Open it with v0.2.0 directly: `agentwatch verify-store`. The chain verifies and
   new records append to the same chain.
4. **Adopt new surfaces if you want them** — none are required:
   - `agentwatch retention apply --profile high-risk-12mo` (or `general-6mo` / `custom`).
   - `agentwatch checkpoint export --sign` + `agentwatch checkpoint rotate` for attribution.
   - `agentwatch compliance report --framework eu-ai-act-art12`.
   - Claude/Gemini/Codex/OpenCode readers via `agentwatch ingest --agent …`.
5. **Run the gates:** `agentwatch verify-store` and `agentwatch verify-privacy` should both pass; `agentwatch
   doctor` reports the new signing/retention state.

## Compatibility promises

- Instrumentation call shapes and read-API field shapes stay source-compatible; additions are additive.
- The store format is unchanged; a v0.1.0 store is never rewritten by an upgrade.
- The legacy `agent_exec_trace` import path keeps working through the shim (DD-12); the codemod is the
  supported way to move off it.
- Any unavoidable break ships with a codemod or a documented step here.

## Verified upgrade

The additive upgrade is frozen against a committed v0.1.0 store vector
(`schema/vectors/store/valid.jsonl`) by [`test_upgrade_v0_1_0.py`](../../../packages/python-sdk/tests/test_upgrade_v0_1_0.py):
the v0.2.0 SDK verifies the v0.1.0 store, reads its records, and appends a v0.2.0 record while the chain stays
green.
