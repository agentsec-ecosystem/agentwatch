# Reference — Backwards-Compatibility Policy

**BLUF:** What we promise not to break, and how deprecation works. DD-12 (preserve shipped API) is the
anchor.

## Stable surfaces

- **Instrumentation SDK** — `@trace_agent`, `plan/tool/retrieval/memory/approval_span`, `TracedGraph`,
  `AgentTracer.setup`, the four privacy modes, version/workload metadata.
- **Read API** — `/runs`, `/runs/{id}`, `/fleet`, `/compare`, `/anomalies` field shapes.
- **Record format** — `schema_version`'d; additive changes only within a major.

## Allowed changes

- Additive fields (new optional fields; new endpoints) — minor version.
- New privacy modes / detectors / views — minor version.
- Breaking changes — major version + deprecation cycle.

## Plugin API (adapter contract) — semver guarantee

The adapter plugin contract ([adapter API](adapter-api.md)) is a **public extension surface**. The names a
community adapter builds against — `HARNESS_ID`, `CAPABILITIES`, `DOCUMENTED_GAPS`, `normalize`, the adapter
error class, `conformance.AdapterSpec`, `conformance.register`, and the conformance runner — are stable and
versioned with `agentwatch.protocol.PROTOCOL_VERSION` under the same rules as above: **additive within a
minor, breaking only in a major with a deprecation cycle**. A registered adapter that does not ship a populated
conformance pack fails CI (O1), so the surface cannot drift silently. Contribute an adapter with the
[contribution guide](../../CONTRIBUTING.md).

## Deprecation cycle

1. Mark the API deprecated in a minor (runtime warning + docs).
2. Keep it functional for one major cycle.
3. Remove in the next major with a codemod or migration guide.

## Compatibility shim (DD-12)

`agent_exec_trace` import paths continue to work via a shim that re-exports from `agentwatch`. The shim is
maintained for at least one major cycle; migrate with the codemod (`scripts/codemod_agent_exec_trace.py`) and
see the [v0.1.0 migration guide](../release/v0.1.0/migration-guide.md). For the v0.1.0 → v0.2.0 upgrade
(additive; a v0.1.0 store verifies in place), see the
[v0.2.0 migration guide](../release/v0.2.0/migration-guide.md).
