# ADR-0006 — Redact before storage

- **Status:** accepted (2026-10-02)
- **Context:** see [design-decisions](../design/design-decisions.md) DD-06.
- **Decision:** Redaction happens at normalization time.
- **Consequences:** Never persist secrets/PII (R7).
