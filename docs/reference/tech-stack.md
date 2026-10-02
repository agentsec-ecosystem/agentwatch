# Reference — Tech Stack

**BLUF:** Python core for parity (DD-01); a thin npx launcher; standard observability stack for the
services (v0.2.0+). Decisions recorded in [design-decisions](../design/design-decisions.md).

## v0.1.0 core

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | matches shipped project |
| CLI | `typer` (or `click`) | `agentwatch` entrypoint |
| Schema models | `pydantic` v2 | record + security-event validation |
| Local socket | Unix domain socket (POSIX) | hook → daemon |
| Store | append-only JSONL + hash chain (DD-08) | `hashlib.sha256` |
| Redaction | rules engine (regex + shape) | see [redaction-rules](../design/redaction-rules.md) |
| Export | `opentelemetry-sdk` + OTLP exporter | OTel GenAI semconv |
| Config | `tomllib` (stdlib, 3.11+) / `tomli` backport | strict validation |
| Tests | `pytest`, `pytest-cov` | coverage ≥95% |
| Lint/types | `ruff`, `mypy --strict` | zero violations |
| Packaging | `hatch` / `build` + `uv` | PyPI `agentwatch` |

## Launcher

| Layer | Choice |
|---|---|
| Node | thin `@agentsec-ecosystem/cli` package |
| Purpose | install hooks, invoke the Python CLI |

## v0.2.0+ services (parity)

| Service | Choice |
|---|---|
| Read API | FastAPI |
| Analytics | Python (polling, rollups, cohorts, detectors) |
| Web UI | React + Vite |
| Trace store | Jaeger / Tempo |
| Ingest | OTel Collector |
| Analytics DB | Postgres 16 |

## Dependencies policy

- Pinned (`uv.lock` / `pip-tools`); Dependabot for bumps; SBOM per release.
- No dependency may add a network call to the v0.1.0 core (local-first, R6).
