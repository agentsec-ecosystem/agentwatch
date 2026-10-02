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

## Parity NFRs

The shipped project's quality bar is retained: ruff zero violations, mypy strict clean, tests green,
coverage >90%.
