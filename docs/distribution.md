# Distribution & Packaging Plan

**BLUF:** One Python core, published to PyPI as `agentwatch`, plus a thin `npx @agentsec-ecosystem/cli`
launcher and a Docker stack for the services.

Status: **draft** (v0.1.0).

## Channels

| Channel | Artifact | Notes |
|---|---|---|
| PyPI | `agentwatch` (free) | CLI + SDK core; `pip` / `uvx` |
| npm | `@agentsec-ecosystem/cli` | Thin launcher that installs/invokes the Python CLI |
| Docker | local stack (API, analytics, web, collector, jaeger/tempo, postgres) | v0.2.0+ |
| GitHub Releases | wheel + sdist + SBOM + provenance | Signed (org supply-chain policy) |

## Decisions

- Name `agentwatch` reserved on PyPI + npm before publish (D2).
- Apache-2.0 with `THIRD_PARTY_NOTICES` crediting MIT `agent-exec-trace` (D1).

## Release checklist

- [ ] ruff/mypy/tests/coverage gates green
- [ ] redaction attack pack clean
- [ ] compatibility table updated
- [ ] security audit published
- [ ] artifacts signed + SBOM
