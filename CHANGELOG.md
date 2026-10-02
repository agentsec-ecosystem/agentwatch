# Changelog

All notable changes to agentwatch are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `agentwatch init` / `agentwatch uninstall` (M3): install Claude Code hooks into
  `.claude/settings.local.json` (or `--scope user`) and start/stop the local daemon; `agentwatch sessions`
  lists recorded sessions; `agentwatch status` reports installed hooks (project/user) and daemon state.
  `PostToolUseFailure` is recorded as `outcome="error"`; hook installation is idempotent and refuses a
  malformed settings file rather than overwriting it (F7).
- Claude Code adapter, hook, and daemon (M3): `agentwatch.adapters.claude_code.normalize`, the
  `agentwatch-hook` fire-and-forget UDS client, and the `agentwatch-daemon` (owner-only socket,
  newline-delimited JSON, JSONL sink) with F2 `hook-error` recording and conformance fixtures.
- `agentwatch.records` (M2): the record + security-event model and strict, reject-never-coerce
  `validate_record()` / `validate_event()` with unknown-version rejection (F8); valid/invalid fixtures and
  a JSON-Schema contract test against `schema/`.
- `agentwatch` CLI (argparse): `status` implemented; `replay`, `export`, `verify-store`, and `migrate`
  wired and failing closed until their milestones (WBS M1).
- Operator configuration loader `agentwatch.configuration` (PRD 16): system < user < project < env < CLI
  precedence, strict unknown-key rejection, and fail-closed export rules (WBS M1).
- `agentwatch` console script, `tomli` backport for Python 3.10, and `python -m build` wheel + sdist
  configuration; `@agentsec-ecosystem/cli` npx launcher (`packages/cli/`) (WBS M1).
- Real CI workflow (ruff, `mypy --strict`, pytest with coverage ≥95% on Python 3.10 and 3.12) (WBS M1).
- Imported the `agent-exec-trace` codebase (MIT, commit `008e1c7`) — `packages/`, `services/`, `apps/`,
  `deploy/`, `examples/`, `scripts/`, and build tooling (WBS M0).
- Complete v0.1.0 documentation set: PRDs 00–14, design (decisions, record format, storage, adapter,
  threat model, privacy, OTel mapping, data dictionary, a11y), reference (API, SDK, adapter conformance,
  compatibility, limitations, detector catalog, record-format spec), machine-readable `schema/`, plans
  (execution, testing & parity), release/migration, runbooks, tutorials, ADRs.
- Governance/DCO/OpenSSF Scorecard automation.

### Changed
- `AGENTWATCH_SOCKET` (the daemon socket selector from the hook contract) is now a reserved environment
  variable and is no longer parsed as a configuration key.
- Porting policy: `agent-exec-trace` is **retained and made private** at v0.1.0 instead of being deleted —
  no repositories are deleted (WBS M13/M15 predecessor retention).

## [0.1.0] - TBD

### Added
- Initial release: Claude Code recording, OTel GenAI export, security-event schema, redaction-by-default,
  local-first hash-chained store, session replay (R1–R8).

[Unreleased]: https://github.com/agentsec-ecosystem/agentwatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/agentsec-ecosystem/agentwatch/releases/tag/v0.1.0
