# Plans

| Document | Scope |
|---|---|
| [v0.1.0 execution plan](v0.1.0-execution-plan.md) | Strategy, sequencing, and the port rule (milestones live in the WBS) |
| [M0 port execution plan](m0-port-execution-plan.md) | Bulk-port `agent-exec-trace` and get the ported suite green |
| [M1 foundation execution plan](m1-foundation-execution-plan.md) | Identity, CLI, configuration, CI, packaging (shipped) |
| [testing-and-parity-strategy.md](testing-and-parity-strategy.md) | Test layers, gates, and the parity suite |
| [demo-and-seed.md](demo-and-seed.md) | Demo + seed data (parity with the shipped project) |
| [M2+M3 schema & adapter execution plan](m2-m3-schema-adapter-execution-plan.md) | Record/event model, Claude Code adapter, hook, daemon |
| [MCP proxy — Plan A (stdio)](mcp-proxy-stdio-execution-plan.md) | M10 N1: MCP adapter, stdio relay, daemon routing, conformance |
| [MCP proxy — Plan B (HTTP/SSE + init)](mcp-proxy-http-execution-plan.md) | M10 N1: HTTP/SSE relay, config install/restore, `init --mcp-proxy` |
| [M10 phases 4–5](m10-phases-4-5-plan.md) | M10: Tier-2 adapters, OTel/NDJSON ingestion, fake-harness emitters, compatibility matrix |
| [M11 fleet + drift](m11-fleet-drift-plan.md) | M11: multi-host fleet aggregation, trailing-baseline drift signals, deployment correlation |
| [M12 NFRs + resilience](m12-nfrs-resilience-plan.md) | M12: store hardening, durability, checkpoints, repair, fault-injection F1–F10, offline/soak CI |
| [M14 engineering rigor](m14-engineering-rigor-plan.md) | M14: property/differential/mutation/fuzz tests, whole-repo CI, perf gate, vectors, forward-compat, error contract, claims ledger, executable docs, WCAG AA, time correctness, signed release |
| [M15 evidence & provenance](m15-evidence-provenance-plan.md) | M15: producer field, annotate, store-access, receipts, BOM, evidence bundle, standalone verifier |
| [v0.2.0-expanded execution plan](v0.2.0-expanded-execution-plan.md) | PRD 49–59: issue-ready backlog, sequencing, cut-line, reserved ADRs 0027–0045, field-test roster |

> **Build risks** were merged into [PRD 08 — Risks](../prd/08-risks.md#build-risks-br1br7).
> Milestones, work items, and exit gates live in the [WBS](../wbs/v0.1.0/wbs-v0.1.0-index.md).
