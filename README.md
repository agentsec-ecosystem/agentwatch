# agentwatch

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/badge/pypi-agentsec--agentwatch-blue.svg)](https://pypi.org/project/agentsec-agentwatch/)
[![Status: v0.1.0](https://img.shields.io/badge/status-v0.1.0-green.svg)](docs/release/v0.1.0/release-notes.md)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://github.com/python/mypy)
[![Coverage](https://img.shields.io/badge/coverage-95%25%20gate-green.svg)](https://github.com/agentsec-ecosystem/agentwatch/actions)
[![OpenSSF Best Practices](https://img.shields.io/badge/OpenSSF-best%20practices-blue.svg)](docs/compliance/openssf-badge.md)
[![Field Test](https://img.shields.io/badge/field%20test-v0.1.0%20%7C%2050%2F50%20cases-brightgreen.svg)](docs/field-test/v0.1.0/FIELD_TEST_REPORT.md)
[![Changelog](https://img.shields.io/badge/changelog-Keep%20a%20Changelog-%23E05735.svg)](CHANGELOG.md)

> **Observability and the security-event record for AI agents.** OpenTelemetry GenAI traces that tell you
> *why* an agent looped, overused a tool, or burned budget — plus the open security-event schema the
> [agentsec-ecosystem](https://github.com/agentsec-ecosystem) is built on.

**Status: v0.1.0 released** — feature-complete, documented, and validated at the release gate. Tagged
`v0.1.0` and published on [PyPI](https://pypi.org/project/agentsec-agentwatch/) — see the
[release notes](docs/release/v0.1.0/release-notes.md).

---

## Install & Quick Start

```sh
pip install agentsec-agentwatch        # Python CLI + SDK (import + CLI: agentwatch)
agentwatch --help                      # list commands

# install hooks + local daemon (monitor-only, zero agent-side code changes)
npx @agentsec-ecosystem/cli init       # or: pipx run agentwatch init

# use Claude Code normally, then reconstruct a session
agentwatch sessions                    # list recorded sessions
agentwatch replay <session-id>         # replay the action timeline
agentwatch verify-store                # verify the hash chain
```

The recording path: `agentwatch-hook` (called by Claude Code's `PreToolUse`/`PostToolUse` hooks) forwards
events to `agentwatch-daemon`, which normalizes them to validated, redacted records. See the
[hook contract](docs/design/claude-code-hook-contract.md). Configuration is layered and fail-closed — see
the [CLI reference](docs/reference/cli-reference.md) and [PRD 16](docs/prd/16-configuration.md).

New here? Follow the [Tutorials](docs/tutorials/README.md), read the
[Architecture tour](docs/design/architecture-tour.md), and keep the
[Runbooks](docs/runbooks/README.md) handy. Upgrading from `agent-exec-trace`? See the
[Migration Guide](docs/release/v0.1.0/migration-guide.md).

---

## Why

Traditional observability tells you a service is up. It does not tell you why an agent called a tool eight
times or drifted into expensive behavior. agentwatch makes agent behavior inspectable — and produces the
record every other security control needs. See [PRD 01](docs/prd/01-why.md).

## What it does

| Capability | Description |
|---|---|
| Behavior record | Every tool call (redacted by default) in OTel GenAI format |
| Security-event schema | `denied` · `policy-fired` · `secret-detected` · `revoked` · `halted` · `drift-detected` |
| Local-first store | Hash-chained, tamper-evident; no egress by default |
| Session replay | Reconstruct any session's action timeline, and replay-as-code for CI |
| Detectors | 43 detectors (35 rule-based + 8 LLM/Claude Code) with structured anomalies |
| Operator views | Fleet Health · Run Timeline · Version Compare · Anomaly Inbox · Agent Detail |
| Harness breadth | Claude Code (full) + provisional modeled Cursor / Codex CLI / Gemini CLI / CrewAI / PydanticAI; MCP interposition proxy (stdio + HTTP/SSE) |

## Compatibility

Claude Code is full-fidelity in v0.1.0; Cursor, Codex CLI, Gemini CLI, CrewAI, and PydanticAI ship as
**provisional (modeled)** adapters until real captures land. Full matrix:
[docs/reference/compatibility.md](docs/reference/compatibility.md).

## Security & supply chain

- **Self-audit, 0 unresolved findings** — [security-audit.md](docs/release/v0.1.0/security-audit.md).
- **No secrets in first-party source or history** — [secret-scan-report.md](docs/release/v0.1.0/secret-scan-report.md)
  (gitleaks + trufflehog + pip-audit; run `make security-scan`).
- **Signed artifacts + SBOM + provenance** on the tag — [release-evidence.md](docs/release/v0.1.0/release-evidence.md);
  local dry-run via `make release-dry-run`.
- **Compliance mapping** — [compliance-matrix.md](docs/release/v0.1.0/compliance-matrix.md) ·
  [OpenSSF checklist](docs/reference/open-source-checklist.md) · [compliance/](docs/compliance/).
- **Disclosure** — [SECURITY.md](SECURITY.md).

## Verification & quality gates

```sh
make setup               # install all packages with dev extras
make test                # pytest + coverage gate (>=95%) + repo guard
make lint                # ruff, zero violations
make typecheck           # mypy --strict
make security-scan       # gitleaks + trufflehog + pip-audit + egress audit
make release-dry-run     # build + CycloneDX SBOM + checksums + verify-release
```

- Field test: **50/50 cases, 226/226 detector scenarios, 49/49 Playwright tests** —
  [FIELD_TEST_REPORT.md](docs/field-test/v0.1.0/FIELD_TEST_REPORT.md).
- Parity gate A1–A6: [parity-checklist.md](docs/release/v0.1.0/parity-checklist.md) (`python scripts/check_parity.py`).
- First-run timing: [first-run-evidence.md](docs/release/v0.1.0/first-run-evidence.md).

## Development

The monorepo holds the Python SDK (`packages/python-sdk`), the API and analytics services
(`services/`), the web console (`apps/web`), and a ported CLI package (`packages/cli`). Layout, setup, and
extending live in the [Development guide](docs/development.md); local stack in
[deployment.md](docs/deployment.md) and the [local-stack runbook](docs/runbooks/deploy-local-stack.md).

```sh
make stack-up            # boot the local docker compose stack (API, web, Postgres, collector, Jaeger)
make web-test            # web unit + axe accessibility tests
make e2e                 # Playwright end-to-end suite
```

## Documentation

Full index: [docs/README.md](docs/README.md).

**Guides**

- [User Guide](docs/guides/user-guide.md) — install, investigate, compare, triage
- [Tutorials](docs/tutorials/README.md) — getting started, instrumenting LangGraph, writing a detector
- [Runbooks](docs/runbooks/README.md) — install/verify, export to OTel, tamper response, upgrade
- [Architecture tour](docs/design/architecture-tour.md) · [Observability](docs/design/observability.md)
- [Development guide](docs/development.md) · [Deployment](docs/deployment.md) · [Glossary](docs/glossary.md)

**Reference**

- [CLI reference](docs/reference/cli-reference.md) · [SDK](docs/reference/sdk.md) ·
  [Adapter API](docs/reference/adapter-api.md) · [API](docs/reference/api.md)
- [Record format spec](docs/reference/record-format-spec.md) · [Store format](docs/reference/store-format.md) ·
  [Detector catalog](docs/reference/detector-catalog.md)
- [Compatibility](docs/reference/compatibility.md) · [Versioning policy](docs/reference/versioning-policy.md) ·
  [Backwards-compatibility policy](docs/reference/backwards-compatibility-policy.md)
- [Errors](docs/reference/errors.md) · [Known limitations](docs/reference/known-limitations.md) ·
  [Performance](docs/reference/performance.md) · [Reference index](docs/reference/README.md)

**Release v0.1.0**

- [Release notes](docs/release/v0.1.0/release-notes.md) · [Migration guide](docs/release/v0.1.0/migration-guide.md)
- [Security audit](docs/release/v0.1.0/security-audit.md) · [Secret scan report](docs/release/v0.1.0/secret-scan-report.md) ·
  [Release evidence](docs/release/v0.1.0/release-evidence.md)
- [Compliance matrix](docs/release/v0.1.0/compliance-matrix.md) · [Parity checklist](docs/release/v0.1.0/parity-checklist.md) ·
  [First-run evidence](docs/release/v0.1.0/first-run-evidence.md)
- [Field test report](docs/field-test/v0.1.0/FIELD_TEST_REPORT.md) · [WBS v0.1.0](docs/wbs/v0.1.0/wbs-v0.1.0-index.md)

**Design & requirements**

- [PRDs](docs/prd/README.md) — why, architecture, landscape, users, features, security, metrics, roadmap
- [Design documents](docs/design/README.md) — subsystem designs, [threat model](docs/design/threat-model.md),
  [design decisions](docs/design/design-decisions.md)
- [Architecture spec](docs/architecture/spec-v0.1.0.md) · [ADRs](docs/adr/) · [Standards](docs/reference/README.md)

## Project

- [Changelog](CHANGELOG.md) · [Roadmap](ROADMAP.md)
- [Contributing](docs/development.md) · [Support](SUPPORT.md)
- [Security policy](SECURITY.md) · [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

## License

Apache License 2.0 — see [LICENSE](LICENSE). Portions credited in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
