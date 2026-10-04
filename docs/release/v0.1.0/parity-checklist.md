# Parity Checklist — v0.1.0

**BLUF:** Every feature that shipped in `agent-exec-trace` v0.1.0 is delivered by agentwatch itself
(PRD 10 matrix A). No row is delegated or waived. The gate is executable.

Status: **passing** · Spec: [PRD 10](../../prd/10-feature-parity.md) · Gate: `scripts/check_parity.py`

## Matrix A

| Row | Capability | Evidence |
|---|---|---|
| A1 | Instrumentation SDK: `@trace_agent` (sync + async), `plan/tool/retrieval/memory/approval_span`, LangGraph `TracedGraph`, PydanticAI adapter, four privacy modes, version/workload metadata | `packages/python-sdk/src/agentwatch/{raw,spans,langgraph,pydantic}.py`; `tests/test_spans.py` |
| A2 | 35 rule detectors + ≥5 optional LLM detectors with structured anomalies | `services/analytics/src/analytics/detectors/` |
| A3 | Analytics pipeline: Jaeger polling, run summaries, fleet rollup + version cohorts | `services/analytics/src/analytics/{ingest,materializer,worker}.py` |
| A4 | Read API: `/runs`, `/runs/{id}`, `/fleet`, `/compare`, `/anomalies` | `services/api/src/api/routes.py` |
| A5 | Web UI: Fleet Health, Run Timeline, Version Compare, Anomaly Inbox, Agent Detail | `apps/web/src/pages/`; `apps/web/src/__tests__/a11y.test.tsx` |
| A6 | Local-first stack, monorepo, Makefile targets, quality gates, demo agent, seed/replay, Playwright E2E, field-test harness | `docker-compose.yml`, `Makefile`, `examples/demo-agent/`, `scripts/seed-e2e-data.py`, `apps/web/tests/e2e/`, `docs/field-test/` |

## Gate

```sh
python scripts/check_parity.py
```

Exits non-zero if any A1–A6 row is missing, so the release gate cannot pass vacuously. Also wired into the
repo guard as `tests/test_parity.py`.

## Release gate status (PRD 07)

- [x] R1–R8 met (records, OTel export, security-event schema, local-first, redaction, replay, inventory, …)
- [x] Replay matches the raw transcript (automated) — `tests/test_replay.py`, transcript import tests
- [x] Redaction attack pack finds 0 secrets — `agentwatch verify-privacy`, selftest
- [ ] Fresh machine → first recorded tool call ≤15 min — evidence in [first-run evidence](first-run-evidence.md)
- [x] Export loads into standard OTel backends — `tests/test_otlp.py`, `tests/test_export.py`
- [x] Full parity A1–A6 delivered + tested — this checklist + `scripts/check_parity.py`
- [x] Fault-injection F1–F10 fail closed — `tests/test_fault_injection.py`
- [ ] Field test + security audit published — see [FIELD_TEST_REPORT.md](../../field-test/v0.1.0/FIELD_TEST_REPORT.md) and [security-audit.md](security-audit.md)
