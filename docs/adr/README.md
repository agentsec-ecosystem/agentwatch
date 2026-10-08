# Architecture Decision Records (ADRs)

Formal records of the accepted decisions. Mirrors [`../design/design-decisions.md`](../design/design-decisions.md).

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-python-core.md) | Python core runtime | accepted |
| [0002](0002-record-format.md) | OTel GenAI record + security-event schema | accepted |
| [0003](0003-local-first.md) | Local-first storage; opt-in export | accepted |
| [0004](0004-adapter-contract.md) | Explicit adapter contract | accepted |
| [0005](0005-schema-upstream.md) | Propose schema upstream to OTel | accepted |
| [0006](0006-redact-before-store.md) | Redact before storage | accepted |
| [0007](0007-hash-chain.md) | Hash-chained store | accepted |
| [0008](0008-jsonl-store.md) | JSONL store for v0.1.0 | accepted |
| [0009](0009-export-gating.md) | Gate export on redaction self-test | accepted |
| [0010](0010-local-measurement.md) | Local-only "kept it on" measurement | accepted |
| [0011](0011-package-names.md) | `agentwatch` package names | accepted |
| [0012](0012-api-compat.md) | Preserve shipped API/instrumentation | accepted |
| [0013](0013-license.md) | Apache-2.0 + third-party notices | accepted |
| [0014](0014-event-naming.md) | Event naming via upstream | deferred |
| [0015](0015-cursor-recording.md) | Cursor recording approach | superseded by 0021 |
| [0016](0016-aat-mapping.md) | AAT mapping & lossless-or-explicit policy | accepted |
| [0017](0017-security-relevant-sampling.md) | Security-relevant sampling | accepted |
| [0018](0018-streaming-views-vs-store-truth.md) | Streaming views vs store truth | accepted |
| [0019](0019-derived-postgres-index.md) | Derived Postgres index | proposed |
| [0020](0020-agent-identity-dimension.md) | Agent identity dimension | accepted |
| [0021](0021-cursor-capture-contract.md) | Cursor capture contract | accepted |
| [0022](0022-gemini-native-telemetry-ingest.md) | Gemini CLI native-telemetry ingest | accepted |
| [0023](0023-mcp-2026-07-28-posture.md) | MCP 2026-07-28 posture | proposed |
| [0024](0024-foreign-data-threat-posture.md) | Foreign-data threat posture | accepted |
| [0025](0025-a2a-interposition.md) | A2A interposition | proposed |
| [0026](0026-naming-decision.md) | Naming decision (`agentwatch`) | **decision required pre-launch** |
| [0028](0028-managed-policy-install.md) | Managed-policy install posture + honest `doctor` | accepted |
| [0029](0029-recorder-attestation.md) | Recorder attestation contents and non-claims | accepted |
| [0030](0030-hook-wallclock-budget.md) | Hook transport & end-to-end wall-clock budget | accepted |
| [0033](0033-range-hash-capture.md) | Content-free range+hash capture | accepted |
| [0040](0040-fleet-role-model.md) | Fleet role x data-class read-access model | accepted |
| [0041](0041-legal-hold.md) | Legal hold suspends retention/purge, with recorded provenance | accepted |
| [0045](0045-standards-participation.md) | Standards participation; closes DD-05 | accepted |
| [0046](0046-retention-and-signing-posture.md) | Retention profiles + signed default posture | accepted |
| [0047](0047-credential-hygiene-observation.md) | Credential-hygiene observation | accepted |
| [0048](0048-plugin-api-versioning.md) | Plugin API versioning promise | accepted |
| [0049](0049-typescript-sdk-decision.md) | TypeScript SDK decision (spike; ship deferred) | accepted |

> ADR numbers **0027–0045** are reserved for the v0.2.0-expanded program (PRD 49–59, milestones M29+); their
> design docs reference the numbers, and the files land with those milestones.
