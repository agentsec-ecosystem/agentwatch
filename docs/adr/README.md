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
| [0015](0015-cursor-recording.md) | Cursor recording approach | deferred |
