# WBS — agentwatch v0.1.0

**BLUF:** v0.1.0 delivers P0 requirements R1–R8 for Claude Code, monitor-only, local-first, with the
security-event schema defined and replay working. Work items are issue-per-item, milestone-tracked.

## Parts & work items

### Part 1 — Foundation (M0)
- 1.1 Repo scaffold (monorepo layout: `packages/`, `services/`, `apps/`, `schema/`, `docs/`)
- 1.2 Python project + `pyproject.toml` (ruff, mypy strict, pytest, coverage>90%)
- 1.3 CLI skeleton (`agentwatch` entrypoint; `init`/`status`/`sessions`/`replay`/`export`/`verify-store`)
- 1.4 Config loader + validation (PRD 16); fail-closed on bad config
- 1.5 CI: ruff/mypy/pytest/coverage; DCO; Scorecard (existing)
- **Exit:** `make setup` works; `agentwatch --help` prints; CI green

### Part 2 — Record format + security-event schema (M1)
- 2.1 Implement `schema/agent-record.schema.json` as a dataclass/Pydantic model
- 2.2 Implement `schema/security-event.schema.json`
- 2.3 Schema validation entry point; reject invalid records (F8)
- 2.4 Versioning + deprecation policy (record-format spec)
- **Exit:** round-trip tests; schema-version enforced; security-event schema published in `schema/`

### Part 3 — Claude Code adapter (M2)
- 3.1 Hook script (Pre/PostToolUse) per the [Claude Code hook contract](../../design/claude-code-hook-contract.md)
- 3.2 Local socket protocol (UDS) between hook and daemon
- 3.3 `normalize(raw) -> Record[]` for Claude Code events
- 3.4 Documented gaps (R3 honesty)
- **Exit:** a Claude Code session emits records; conformance fixtures green

### Part 4 — Local daemon + storage (M2)
- 4.1 Daemon: listen on UDS, receive events
- 4.2 Normalizer + redactor pipeline (DD-06)
- 4.3 Append-only JSONL store + hash chain (DD-07, DD-08)
- 4.4 Retention (size/time caps, R11 early)
- **Exit:** records stored, chain `verify-store` clean, no network required (R6)

### Part 5 — Redaction-by-default (M2)
- 5.1 Redaction rules engine (see [redaction-rules.md](../../design/redaction-rules.md))
- 5.2 Four privacy modes (metadata-only/truncated/hashed/full)
- 5.3 Redaction self-test (blocks export, DD-09)
- **Exit:** attack pack finds 0 leaks in store (R7)

### Part 6 — OTel GenAI export (M3)
- 6.1 OTLP exporter (opt-in)
- 6.2 Attribute mapping ([otel-mapping.md](../../design/otel-mapping.md))
- 6.3 Export gating on redaction self-test
- **Exit:** traces load in ≥2 backends unmodified (R4)

### Part 7 — Session replay (M3)
- 7.1 `agentwatch sessions` (list)
- 7.2 `agentwatch replay <id>` (ordered timeline)
- 7.3 Replay-fidelity automated test vs raw transcript
- **Exit:** replay matches transcript (R8)

### Part 8 — CLI + first-run (M4)
- 8.1 `agentwatch init` (install hooks + start daemon; monitor-only default)
- 8.2 `agentwatch status` (health summary, PRD 13)
- 8.3 `/healthz` endpoint
- 8.4 First-run guide verification (≤15 min on clean machine)
- **Exit:** fresh machine → first recorded call ≤15 min (R2, CUJ-1)

### Part 9 — Field test + release readiness (M5)
- 9.1 Field-test execution (see [field-test-plan.md](../../field-test/v0.1.0/field-test-plan.md))
- 9.2 Security audit (see [release/v0.1.0/security-audit.md](../../release/v0.1.0/security-audit.md))
- 9.3 Release notes + compatibility table + SBOM + signed artifacts
- 9.4 Tag v0.1.0
- **Exit:** all P0 met; field test report published; release shipped

## Milestones

| M | Parts | Gate |
|---|---|---|
| M0 | 1 | foundation green |
| M1 | 2 | schema + validation |
| M2 | 3, 4, 5 | record + store + redaction |
| M3 | 6, 7 | export + replay |
| M4 | 8 | first-run ≤15 min |
| M5 | 9 | field test + release |
