# ADR-0026 — Naming decision (agentwatch)

- **Status:** accepted — **decision: full rename at v0.2.0 (option D)** (2026-10-05)
- **Decision:** **D — full rename at v0.2.0.** The distribution, import module, and CLI are renamed at the
  v0.2.0 release. The target name is **TBD** and must be recorded here before M30's 30.16 ("Execute the
  ADR-0026 naming outcome"); until it is pinned, the rename is tracked as a cross-cutting work item, not
  started. This supersedes the earlier A-or-C recommendation.
- **Consequences (accepted):** breaks the just-shipped v0.1.0 identity and ecosystem references and carries
  the highest cost — a migration guide, alias/shim for `import agentwatch` and the `agentwatch` CLI across
  the v0.2.x window, updates to every doc/example/compatibility row, and the npx launcher. Every package
  version string must move together (M30 30.3 "single-version consistency").
- **Context:** The name `agentwatch` is used by five or more active projects, several in the exact category
  (`agentwatch-core`, `agentwatch-monitor`, `agentwatch-io` on PyPI; `@nicofains1/agentwatch` on npm;
  `sreerevanth/AgentWatch`; `dhanraj176/agentwatch`, a near-identical MCP-proxy recorder; plus a Berkeley CLTC
  research report titled "AgentWatch"). Our package is `agentsec-agentwatch`, but the import name and CLI are
  `agentwatch`, so `pip install agentwatch` installs a different, unaudited project — a support and
  supply-chain-reputation risk. No trademark is held by us for "agentwatch" (verify; not legal advice).
- **Actions that happen regardless:** fully-qualified install in every doc example; a distribution-check
  warning in `--version`/`init`/`doctor` (detect the wrong package); an honest namesake FAQ.
