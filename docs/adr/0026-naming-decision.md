# ADR-0026 — Naming decision (agentwatch)

- **Status:** proposed — **decision required before the v0.2.0 launch** (2026-10-05)
- **Context:** The name `agentwatch` is used by five or more active projects, several in the exact category
  (`agentwatch-core`, `agentwatch-monitor`, `agentwatch-io` on PyPI; `@nicofains1/agentwatch` on npm;
  `sreerevanth/AgentWatch`; `dhanraj176/agentwatch`, a near-identical MCP-proxy recorder; plus a Berkeley CLTC
  research report titled "AgentWatch"). Our package is `agentsec-agentwatch`, but the import name and CLI are
  `agentwatch`, so `pip install agentwatch` installs a different, unaudited project — a support and
  supply-chain-reputation risk. No trademark is held by us for "agentwatch" (verify; not legal advice).
- **Decision (options):** (A) keep `agentwatch`, own the disambiguation; (B) keep the package, change import/CLI
  namespace; (C) distinctive product name, keep the module; (D) full rename at v0.2.0. Recommendation to record in
  the ADR: **A or C, decided before launch**, because every option gets more expensive after press/standards cycles.
- **Actions that happen regardless:** fully-qualified install in every doc example; a distribution-check warning in
  `--version`/`init`/`doctor` (detect the wrong package); an honest namesake FAQ.
- **Consequences:** Protects install integrity and claim clarity; a rename carries the highest cost and breaks the
  just-shipped v0.1.0 identity and ecosystem references.
