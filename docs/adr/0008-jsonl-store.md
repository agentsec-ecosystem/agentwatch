# ADR-0008 — JSONL store for v0.1.0

- **Status:** accepted (2026-10-02)
- **Context:** see [design-decisions](../design/design-decisions.md) DD-08.
- **Decision:** Append-only JSONL + hash chain; Postgres for analytics in v0.2.0.
- **Consequences:** Simple, local-first, tamper-evident; matches the shipped analytics stack when it lands.
