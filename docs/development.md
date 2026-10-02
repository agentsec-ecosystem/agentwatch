# Development Guide

**BLUF:** How to work on agentwatch: layout, setup, quality gates, and how to extend it.

## Repository layout (target / parity)

```
packages/   SDK (Python)
services/   analytics, api
apps/       web (React)
deploy/     docker-compose, configs
examples/   demo agents
tests/      unit + e2e
docs/       this documentation
schema/     machine-readable contracts
```

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # or: uv sync
make setup
```

## Quality gates (must be green)

```sh
make lint        # ruff — zero violations
make typecheck   # mypy — strict, clean
make test        # pytest — green, coverage >90%
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
