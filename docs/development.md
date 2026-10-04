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
make web-install # npm ci (web)
make web-typecheck
make web-test    # vitest + axe accessibility checks
make e2e         # Playwright against the compose stack
make stack-smoke # compose builds, boots, and serves API + web
make stack-up    # local stack (v0.2.0+)
```

CI runs exactly these targets. Workflows and their required/informational status:

| Workflow | Scope | Status |
|---|---|---|
| `ci.yml` | ruff, `mypy --strict`, pytest + coverage on 3.10/3.12 | **required** |
| `web.yml` | web type-check + unit + axe (M14 Q5) | **required** |
| `offline-e2e.yml` | no-network recording claim + egress audit | **required** |
| `e2e.yml` | Playwright against the compose stack (M14 Q5); includes the a11y contrast + keyboard journey (Q11) | **required** |
| `stack-smoke.yml` | compose builds/boots and serves API + web (M14 Q5) | informational (path-filtered) |
| `perf.yml` | NFR-1 p99 + drift gate (M14 Q4) | **required** on perf paths |
| `mutation.yml` | trust-path mutation gate (M14 Q2) | **required** on trust paths |
| `claims.yml` | public claims trace to live evidence (M14 Q9) | **required** on ledger paths |
| `docs.yml` | J3 cookbook commands run offline on the seed dataset (M14 Q10) | **required** on cookbook paths |
| `fuzz.yml` | nightly parser fuzzing (M14 Q3) | informational (nightly) |
| `soak.yml` | nightly soak (M12) | informational (nightly) |
| `scorecard.yml` / `dco.yml` | supply-chain scorecard / DCO sign-off | **required** |
| `release.yml` | on tag: build + SBOM + cosign signature + SLSA L3 provenance + `verify-release` gate (M14 Q13) | release gate |

Compose-backed jobs (`e2e.yml`, `stack-smoke.yml`) skip with an explicit reason when Docker is
unavailable; they never silently pass. Sign commits with `git commit -s` (DCO).

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
