# Known-Limitations Shrink — v0.2.0 (32.17)

**BLUF:** The v0.2.0 release gate requires **G1/G2/G4/G7/G8** to leave
[`known-limitations.md`](../../reference/known-limitations.md) **with a proving test**; the others leave if their
owning PRD landed, else carry forward **explicitly by name**. A limitation leaves that file only when a test
proves it closed (the file's own policy).

Gap register: [PRD 40 §1a](../../prd/40-v0.2.0-program.md).

## Release-gate gaps (must leave)

| Gap | v0.1.0 | v0.2.0 | Proving test | Field case |
|---|---|---|---|---|
| **G1** batch polling (~30 s), not streaming | open | **closed** | `test_live_tail.py`, `test_streaming_soak.py` | FT-STR-1, FT-STR-2 |
| **G2** no distributed trace correlation | open | **closed** | `test_trace.py`, `test_session_correlation.py` | FT-TRACE-1, FT-TRACE-2 |
| **G4** 28/35 rule detectors silent | open | **closed** | `services/analytics/tests/test_detector_non_silent.py` | FT-DET-2 (≥80% non-silent) |
| **G7** OTLP JSON only (no gRPC/protobuf) | open | **closed** | `test_otlp.py`, `test_otlp_protobuf_ingest.py` | FT-OTEL-1, FT-OTEL-2 |
| **G8** hash chain detect-only; signing opt-in/unreleased | open | **closed** | `test_signing_posture.py` | FT-CMP-2 (signed default verifies end-to-end) |

## Other gaps (leave if the owning PRD landed, else carried by name)

| Gap | v0.2.0 status | Evidence |
|---|---|---|
| G3 no multi-tenant isolation | **carried (named)** — Postgres fleet tier re-sequenced behind the embedded index (ADR-0035); not built | ADR-0035; known-limitations |
| G5 adapters "modeled" | **partial** — Cursor + Codex now `fixture-verified` (native-hooks / rollout reader); Gemini/CrewAI/PydanticAI still provisional | `testkit/`; FT-CUR-1/2 |
| G6 MCP relayed not recorded | **closed (M27)** | `test_mcp_surface.py`; FT-MCP-1/2 |
| G9 memory-audit / injection signal | **partial** — memory read/write/delete recorded + `search --memory`; a dedicated memory-audit **UI** still absent | `test_memory_surface.py`; FT-DET-4/7 |
| G10 LLM detectors research-grade | **closed** — LLM detectors on the shared offline harness with a quality bar | `services/analytics/tests/test_llm_eval.py`; FT-DET-3 |
| G11 no agent identity | **closed** | `test_identity.py`, `test_credential_hygiene.py`; FT-IDN-1/3 |
| G12 compliance mappings are docs only | **closed** — `compliance report` (ISO/EU/NIST/SOC2 + OWASP ASI) | `test_compliance.py`, `test_compliance_asi.py`; FT-CMP-1, FT-ASI-1 |

## Carry-forwards (named, not dropped)

The following remain in [`known-limitations.md`](../../reference/known-limitations.md) by name: multi-tenant
isolation (G3), the provisional modeled adapters (Gemini/CrewAI/PydanticAI), the memory-audit **UI**, and the
declared M29/M30 gaps (system-effects Linux-only, ACS revision-pinned, framework recipes blocked, etc.).
