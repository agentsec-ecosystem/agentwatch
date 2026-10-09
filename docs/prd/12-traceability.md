# PRD 12 — Requirements Traceability Matrix

**BLUF:** Every v0.1.0 requirement ties to a user journey, a WBS part, an acceptance test, and (where
applicable) a shipped-feature **parity row**. Nothing is orphaned. **v0.2.0** requirements are added below the
same way — each ties to its CUJ, WBS work item, proving test, and field case.

**Status:** v0.1.0 + v0.2.0 · **Parent:** agentsec-ecosystem #209

## v0.1.0 requirements

| Req | CUJ | Milestone | Acceptance test | Parity row |
|---|---|---|---|---|
| R1 record every tool call | CUJ-1 | M1, M2, M3 | session timeline reconstructs from store | A1 (behavior trace schema) |
| R2 zero code changes, ≤15 min | CUJ-1 | M2, M5 | fresh-machine install, first call recorded | A1 (SDK path) |
| R3 Claude Code coverage | CUJ-1 | M2 | Pre/PostToolUse captured; gaps documented | extra (coding agents) |
| R4 OTel GenAI export | CUJ-3 | M4 | loads into ≥2 standard backends unmodified | A1 (OTLP) |
| R5 security-event schema | CUJ-4 | M1, M3 | fixture events validate against schema; ≥1 sibling emits | extra |
| R6 local-first storage | CUJ-1 | M3 | core works with no network | A1 (local store) |
| R7 redaction-by-default | CUJ-1 | M3 | attack pack finds zero secrets in store | A1 (4 privacy modes) |
| R8 session replay | CUJ-2 | M4 | replay matches raw transcript (automated) | A1 (run timeline) |

## P1/P2 + cross-cutting requirements (also v0.1.0)

| Item | Milestone | Acceptance |
|---|---|---|
| R9 shadow-agent / MCP inventory | M9 | inventory lists local agents/servers |
| R10 harness/framework expansion | M10 | ≥5 Tier-1 + ≥3 Tier-2 adapters |
| R11 retention + hash-chaining | M9 | retention enforced; `verify-store` clean |
| R12 local replay viewer | M7 | viewer renders (parity A5) |
| R13 fleet aggregation | M11 | multi-host aggregation (opt-in) |
| NFR-1..NFR-12 (PRD 13) | M12 | perf, sizing, self-observability, a11y, i18n |
| F1–F10 (PRD 17) | M12 | every failure fails closed / surfaced |
| Compliance (PRD 18) | M13 | OWASP matrix + OpenSSF checklist |

## v0.2.0 requirements (PRD 40–59)

Each requirement ties to a CUJ, the owning milestone work item, a proving test, and the field case that ran it.

| Requirement (PRD) | CUJ | Work item | Proving test | Field case |
|---|---|---|---|---|
| AAT emit/ingest + external verification (41) | CUJ-15 | AAT-1..5 | `test_aat*.py`, `schema/vectors/verify_aat.py` | FT-AAT-1/2/3 |
| OTel agent spans + OTLP/gRPC + two backends (41) | CUJ-3 | OTEL-1..3 | `test_otel*.py`, `test_otlp*.py` | FT-OTEL-1/2/3/4, FT-BACKEND-2 |
| Cross-agent trace correlation (41) | CUJ-16 | TRACE-1..2 | `test_trace.py` | FT-TRACE-1/2 |
| Harness fidelity — Cursor/Codex/Gemini (42/45/47) | CUJ-1 | CUR-1..3, COD-1, GEM-1..2 | `testkit/`, `test_cursor_*`, `test_codex_*`, `test_gemini_*` | FT-CUR-1/2, FT-COD-1, FT-GEM-1 |
| MCP full surface (42) | CUJ-3 | MCP-1..6 | `test_mcp_surface.py` | FT-MCP-1/2 |
| Streaming (42) | CUJ-17 | STR-1..3 | `test_live_tail.py`, `test_streaming_soak.py` | FT-STR-1/2 |
| Detector credibility + corpus (43) | CUJ-19 | DET-1..7, COR-1 | `test_detector_*.py` | FT-DET-1..7, FT-COR-1/2 |
| Identity + credential class (44) | CUJ-14/16 | IDN-1..3 | `test_identity.py`, `test_credential_hygiene.py` | FT-IDN-1/2/3 |
| Compliance report + signing (44) | CUJ-18 | CMP-1..4 | `test_compliance*.py`, `test_signing_posture.py` | FT-CMP-1/2/3 |
| SIEM / OCSF / Syslog (44) | CUJ-18 | SIEM-1 | `test_siem_consumers.py`, `test_siem_syslog.py` | FT-SIEM-1 |
| A2A interposition + signed card (45) | CUJ-20 | A2A-1..2 | `test_a2a_*.py` | FT-A2A-1 |
| Approval provenance v2 (49) | CUJ-21 | APV-1..3 | `test_authorization.py`, `test_permission_mode.py`, `test_oversight.py` | FT-APV-1/2/3 |
| Deployability + attestation (50) | CUJ-25 | DEP-1..3 | `test_signing_posture.py`, `test_doctor.py` | FT-DEP-1/2/3 |
| Native OTel + framework reach (51) | CUJ-28 | CCO-1..2, FWK-1..2 | `test_claude_otel.py`, `test_claude_agent_sdk.py`, `test_frameworks.py` | FT-CCO-1/2, FT-FWK-1/2 |
| Capability supply chain + memory (52) | CUJ-23 | CAP-1..3, MEM-1 | `test_capability_drift.py`, `test_memory_*.py` | FT-CAP-1/2, FT-MEM-1 |
| Code provenance + Agent Trace (53) | CUJ-22 | PRV-1..3 | `test_provenance.py`, `test_code_provenance.py` | FT-PRV-1/2/3 |
| Console + query tier (54) | CUJ-24 | LUI-1..2 | `test_console.py`, `test_query_index.py` | FT-LUI-1/2 |
| Agent interfaces + policy (55) | CUJ-26/27 | AGI-1..2, POL-1..2 | `test_mcp_server.py`, `test_policy_*.py` | FT-AGI-1/2, FT-POL-1 |
| Governance/retention/redaction (56) | CUJ-31/32 | ACC-1..2, HLD-1, RED-1 | `test_access.py`, `test_legal_hold.py`, `test_redact_eval.py` | FT-ACC-1/2, FT-HLD-1, FT-RED-1 |
| Investigation depth + verifier (57) | CUJ-8 ext/34 | ENV-1, VFY-1, IR-1, CNC-1, SBX-1 | `test_environment_fingerprint.py`, `test_browser_verifier.py`, `test_incident_cases.py`, `test_concurrency.py`, `test_sandbox_events.py` | FT-ENV-1, FT-VFY-1, FT-IR-1, FT-CNC-1, FT-SBX-1 |
| Outcomes/ephemeral/growth (58) | CUJ-29/30 | OUT-1..2, RUN-1, NTF-1, DEMO-1, API-1, EXA-1, SDK-1, TSS-1 | `test_outcomes.py`, `test_runner_segments.py`, `test_alert_recipes.py`, `test_openapi_contract.py`, `test_examples_gallery.py`, `test_sdk.py` | FT-OUT-1/2, FT-RUN-1, FT-NTF-1, FT-DEMO-1, FT-API-1, FT-EXA-1, FT-SDK-1, FT-TSS-1 |
| OWASP ASI + standards (59) | CUJ-18 ext | ASI-1, STD-1 | `test_compliance_asi.py` | FT-ASI-1 |
| Governance/plugin + naming (46) | — | GOV-1, NAM-1 | `test_codemod_agent_exec_trace.py`, `test_conformance_runner.py`, `naming_guard` | FT-GOV-1, FT-ENV-0 |
| Cross-harness test kit (47) | — | XHT-1..4 | `xht_replay`, `test_frameworks.py` | FT-XHT-1/2/3/4 |

Full case roster: [`docs/field-test/v0.2.0/FIELD_TEST_REPORT.md`](../field-test/v0.2.0/FIELD_TEST_REPORT.md).

## Parity rows (agent-exec-trace shipped → PRD 10 matrix A)

| Parity row | Agentwatch version | Verification |
|---|---|---|
| A1 instrumentation SDK (spans, LangGraph, OTLP, privacy modes, metadata) | v0.2.0 | SDK conformance tests |
| A2 40 detectors (35 rule + 5 LLM) | v0.3.0 | detector unit + corpus tests |
| A3 analytics pipeline (rollups, cohorts) | v0.2.0 | pipeline tests |
| A4 read API (`/runs`, `/fleet`, `/compare`, `/anomalies`) | v0.2.0 | API contract tests |
| A5 operator UI (Fleet, Timeline, Compare, Inbox, Agent Detail) | v0.3.0–v1.0 | E2E Playwright |
| A6 stack/tooling/field-test | v0.2.0–v1.0 | CI + field test |

## Rule

A requirement or parity row without a linked acceptance test is not "done". The v1.0 parity gate re-checks
**every** matrix-A row.
