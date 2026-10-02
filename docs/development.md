# Development Guide

**BLUF:** How to work on agentwatch: layout, setup, quality gates, and how to extend it.

## Repository layout (ported in M0)

The tree below was ported from `agent-exec-trace` at commit `008e1c7` (MIT; see
[THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)). The Python namespace is `agentwatch`; the legacy
`agent_exec_trace` import path is served by a compatibility shim (DD-12).

```
packages/python-sdk/   agentwatch SDK (instrumentation, redaction, CLI, config)
packages/cli/          @agentsec-ecosystem/cli npx launcher (Node)
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

The `agentwatch` console script and its argparse framework live in
`packages/python-sdk/src/agentwatch/cli/`; the operator config loader is
`packages/python-sdk/src/agentwatch/configuration.py` (PRD 16). See the
[CLI reference](reference/cli-reference.md).

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
make setup        # editable-installs the three packages with their [dev] extras
```

## Quality gates (must be green)

```sh
make lint        # ruff — zero violations
make typecheck   # mypy — strict, clean
make test        # pytest — green, coverage ≥95% + the repo guard
make stack-up    # local stack (v0.2.0+)
```

CI runs exactly these targets (`.github/workflows/ci.yml`) on Python 3.10 and 3.12, plus the DCO check
(`.github/workflows/dco.yml`) on every PR. Sign commits with `git commit -s`.

### Configuration

The operator config loader (`agentwatch.configuration`, PRD 16) is layered and fail-closed. Run
`agentwatch status` to print the resolved configuration, or `agentwatch --set log.level=debug status` to
override one key. Precedence, defaults, and the strict-validation rules are in the
[CLI reference](reference/cli-reference.md) and [PRD 16](prd/16-configuration.md).

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
