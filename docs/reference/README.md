# Reference

| Document | Scope |
|---|---|
| [API](api.md) | Read API surface (`/runs`, `/fleet`, `/compare`, `/anomalies`) |
| [SDK](sdk.md) | Instrumentation SDK (`@trace_agent`, spans, adapters) |
| [Adapter conformance](adapter-conformance.md) | How harness/framework adapters are verified |
| [Compatibility](compatibility.md) | Harness × version matrix |
| [Known limitations](known-limitations.md) | Honest gaps, including inherited ones |
| [Detector catalog](detector-catalog.md) | The 40 detectors by category |
| [Record format spec](record-format-spec.md) | Normative record + security-event contract, versioning/deprecation |
| [Store format](store-format.md) | Envelope, chain, tombstones, marker records, vectors |
| [Evidence verifier](evidence-verifier.md) | Standalone, dependency-free bundle/store verifier (M15 S12) |
| [Tech stack](tech-stack.md) | Languages, libs, services, dependencies policy |
| [CLI reference](cli-reference.md) | Subcommands, global flags, config precedence, exit codes |
| [Versioning policy](versioning-policy.md) | SemVer, support windows, backports |
| [Backwards-compatibility policy](backwards-compatibility-policy.md) | Stable surfaces, deprecation cycles |
| [Comparison](comparison.md) | vs adjacent tools |
| [i18n & locale](i18n.md) | UTC timestamps; English-first; full i18n deferred |
| [Resource cost](resource-cost.md) | CPU/memory/disk/network to the operator |
| [Performance](performance.md) | Recording-path p99 latency vs NFR-1, generated from a run (Q4) |
| [Open-source checklist](open-source-checklist.md) | OpenSSF readiness mapping |
