# ADR-0022 — Gemini CLI native-telemetry ingest

- **Status:** proposed (2026-10-05, v0.2.0)
- **Context:** see [PRD 42](../prd/42-harness-fidelity-and-realtime.md) GEM-1..2. Gemini CLI ships built-in
  OpenTelemetry (`.gemini/settings.json` `telemetry`), OTLP gRPC/HTTP, with `session.id`, `installation.id`,
  `active_approval_mode`, `user.email`.
- **Decision:** Support Gemini via native-OTel ingest (settings recipe or `outfile` → `ingest --format otel`) rather
  than a bespoke adapter; map `active_approval_mode` → approval provenance, `user.email` → principal (hashed by
  default); **mandatory** redaction because `logPrompts` defaults true.
- **Consequences:** Full fidelity at S–M cost; the privacy pipeline is load-bearing on this path; attribute drift
  needs version-pinned fixtures.
