<p align="center">
  <img src="https://img.shields.io/badge/status-pre--v0.1.0-orange.svg" alt="status pre-v0.1.0">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-Apache--2.0-green.svg" alt="Apache-2.0">
  <a href="https://www.bestpractices.dev/"><img src="https://img.shields.io/badge/OpenSSF-passing-blue" alt="OpenSSF Best Practices"></a>
  <a href="https://github.com/agentsec-ecosystem/agentwatch/actions/workflows/scorecard.yml"><img src="https://img.shields.io/badge/Scorecard-checking-lightgrey" alt="OpenSSF Scorecard"></a>
</p>

# agentwatch

**Observability and the security-event record for AI agents.** OpenTelemetry GenAI traces that tell you
*why* an agent looped, overused a tool, or burned budget — plus the open security-event schema the
[agentsec-ecosystem](https://github.com/agentsec-ecosystem) is built on.

> **Status: v0.1.0 in progress — docs complete; build next.** agentwatch is the **shipped-feature superset**
> of `agent-exec-trace`: that codebase is **ported in first (WBS M0)** and the old repo is **deleted** at
> v0.1.0 release.

## Quickstart

```sh
# install hooks + local daemon (monitor-only, zero agent-side code changes)
npx @agentsec-ecosystem/cli init      # or: pipx run agentwatch init

# use Claude Code normally, then reconstruct a session
agentwatch sessions
agentwatch replay <session-id>
```

## What it does

| Capability | Description |
|---|---|
| Behavior record | Every tool call (redacted by default) in OTel GenAI format |
| Security-event schema | `denied` · `policy-fired` · `secret-detected` · `revoked` · `halted` |
| Local-first store | Hash-chained, tamper-evident; no egress by default |
| Session replay | Reconstruct any session's action timeline |
| Detectors | 40 signals (35 rule-based + 5 LLM) restored from the shipped project |
| Operator views | Fleet Health · Run Timeline · Version Compare · Anomaly Inbox · Agent Detail |

## Why

Traditional observability tells you a service is up. It does not tell you why an agent called a tool eight
times or drifted into expensive behavior. agentwatch makes agent behavior inspectable — and produces the
record every other security control needs. See [PRD 01](docs/prd/01-why.md).

## Compatibility

Claude Code at v0.1.0; Cursor in v0.1.x; Codex/Gemini and frameworks by v0.3.0. Matrix:
[docs/reference/compatibility.md](docs/reference/compatibility.md).

## Documentation

Start at [docs/](docs/README.md) · [PRDs](docs/prd/README.md) · [User Guide](docs/USER_GUIDE.md) ·
[Architecture tour](docs/design/architecture-tour.md) · [Roadmap](ROADMAP.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE). Portions credited in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
