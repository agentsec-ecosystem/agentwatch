# Reference — Namesake FAQ (agentwatch)

**BLUF:** The Python import name `agentwatch` (and the `agentwatch` CLI) is used by several unrelated
projects. **Always install fully-qualified:** `pip install agentsec-agentwatch`. This page is the honest
disambiguation required by [ADR-0026](../adr/0026-naming-decision.md).

## Which package is this project?

| | |
|---|---|
| Distribution | `agentsec-agentwatch` |
| Import | `agentwatch` |
| CLI | `agentwatch` |
| Repo | `agentsec-ecosystem/agentwatch` |
| Fully-qualified install | `pip install agentsec-agentwatch` |

## I ran `pip install agentwatch` — what did I get?

Probably **not** this project. `agentwatch` on PyPI is a namesake package, and at least five projects use the
name (including a near-identical MCP-proxy recorder and a research report titled "AgentWatch"). The bare name
is a support and supply-chain-reputation risk, so agentwatch ships a **distribution check**:

- `agentwatch --version`, `agentwatch init`, and `agentwatch doctor` warn loudly when the `agentwatch` module
  was provided by a distribution other than `agentsec-agentwatch`.
- `agentwatch doctor` reports a `distribution` check: PASS when it is ours, WARN otherwise.

## How do I fix it?

```bash
pip uninstall agentwatch          # remove the namesake if present
pip install agentsec-agentwatch   # the real project
agentwatch doctor                 # distribution check should be PASS
```

## What about the v0.2.0 rename?

ADR-0026 records the decision to **fully rename at v0.2.0** (target name TBD). Until that lands, the
fully-qualified install and the distribution check are the guardrails; the rename is tracked with an
`import agentwatch` / CLI shim so v0.1/v0.2 users are not broken.