# ADR-0015 — Cursor recording approach

- **Status:** deferred (2026-10-02)
- **Context:** see [design-decisions](../design/design-decisions.md) DD-15.
- **Decision:** Native hooks first; proxy-interpose only classes native cannot capture.
- **Consequences:** Maximize fidelity, minimize proxies (deferred).
