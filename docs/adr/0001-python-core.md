# ADR-0001 — Python core runtime

- **Status:** accepted (2026-10-02)
- **Context:** see [design-decisions](../design/design-decisions.md) DD-01.
- **Decision:** The core is Python (SDK + analytics + API); `npx` is a thin launcher.
- **Consequences:** True parity with the shipped `agent-exec-trace` Python SDK/services; preserves instrumentation and read-API contracts.
