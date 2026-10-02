# Development Guide

**BLUF:** How to work on agentwatch: layout, setup, quality gates, and how to extend it.

## Repository layout (ported in M0)

The tree below was ported from `agent-exec-trace` at commit `008e1c7` (MIT; see
[THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)). The Python namespace is `agentwatch`; the legacy
`agent_exec_trace` import path is served by a compatibility shim (DD-12).

```
packages/python-sdk/   agentwatch SDK (instrumentation + redaction)
services/analytics/    analytics pipeline + detectors
services/api/          FastAPI read API
apps/web/              React operator UI (Vite)
deploy/                docker-compose + collector configs
examples/              demo agents
scripts/               seed/export helpers
tests/                 repo-level tests
docs/                  this documentation
schema/                machine-readable contracts
```

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
make setup        # editable-installs packages/python-sdk, services/api, services/analytics
```

## Quality gates (must be green)

```sh
make lint        # ruff — zero violations
make typecheck   # mypy — strict, clean
make test        # pytest — green, coverage ≥95%
make stack-up    # local stack (v0.2.0+)
```

## Extending

- **Add a detector** — see [tutorials/04-write-a-detector.md](tutorials/04-write-a-detector.md);
  register in the detector engine; add corpus fixture + unit test; update the
  [detector catalog](reference/detector-catalog.md).
- **Add a harness adapter** — implement the [adapter contract](reference/adapter-conformance.md); declare
  capability gaps explicitly; add conformance fixtures.

## Commits & PRs

- Commits need a **DCO** sign-off: `git commit -s`.
- PRs run DCO + CI; `main` is protected (PR + green checks).
- Keep changes focused; update docs and the [traceability matrix](prd/12-traceability.md) when requirements
  move.
