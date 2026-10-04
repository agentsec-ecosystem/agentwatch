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

## Deprecation cycle

1. Mark the API deprecated in a minor (runtime warning + docs).
2. Keep it functional for one major cycle.
3. Remove in the next major with a codemod or migration guide.

## Compatibility shim (DD-12)

`agent_exec_trace` import paths continue to work via a shim that re-exports from `agentwatch`. The shim is
maintained for at least one major cycle; see the [migration guide](../release/v0.1.0/migration-guide.md).
