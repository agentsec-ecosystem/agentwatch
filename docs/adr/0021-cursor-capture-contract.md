# ADR-0021 — Cursor capture contract

- **Status:** accepted (2026-10-05, v0.2.0) — implemented · **Supersedes:** ADR-0015 (deferred)
- **Context:** see [PRD 42](../prd/42-harness-fidelity-and-realtime.md) CUR-1..3. Cursor ships native `hooks.json`
  across the full agent loop (incl. blocking hooks); Elastic proved the deployment at scale.
- **Decision:** Capture Cursor via its native hooks (consent-first install, byte-identical restore). Subscribe to
  blocking before-events for telemetry but **never answer them** (monitor-only, R2). Tag IDE/CLI/remote via env
  vars. Cloud-agent hook gaps are declared, not silent.
- **Consequences:** Full-fidelity Cursor including file reads/reasoning; ADR-0015's "proxy only where native cannot"
  is now the fallback only; version-tagged corpus + drift required.
