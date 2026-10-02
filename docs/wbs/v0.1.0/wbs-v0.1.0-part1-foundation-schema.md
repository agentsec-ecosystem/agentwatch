# WBS v0.1.0 — Part 1: Foundation & Schema (M0–M1)

**BLUF:** Establish the repo/CLI/CI foundation by **porting the `agent-exec-trace` layout first**, then
implement the normative record + security-event schema. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M0 — Foundation

**Goal:** a running, lint-clean, tested skeleton — **ported and adapted** from `agent-exec-trace`, not
greenfield.

**Requirements / PRDs:** NFR-11, [PRD 16](../../prd/16-configuration.md),
[development guide](../../development.md), [PRD 10](../../prd/10-feature-parity.md) (port rule).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 0.1 | **Port** monorepo layout from `agent-exec-trace` (`packages/`, `services/`, `apps/`, `examples/`, `tests/`, `deploy/`) | agentwatch layout | dirs mirror the shipped repo |
| 0.2 | **Port** `pyproject.toml` + tooling (ruff, mypy strict, pytest, coverage, Makefile targets) | build/test config | `make setup`, `make lint`, `make test` work |
| 0.3 | CLI skeleton (`agentwatch` entrypoint; all subcommands stubbed) | [cli-reference](../../reference/cli-reference.md) realized | `agentwatch --help` lists commands |
| 0.4 | Config loader + validation (precedence, strict, **fail-closed**) | [PRD 16](../../prd/16-configuration.md) realized | valid loads; invalid refuses to start (F7) |
| 0.5 | CI pipeline (ruff, mypy, pytest, **coverage ≥95%**, DCO) | GitHub Actions | CI green on PR |
| 0.6 | Packaging (wheel + sdist; console script) | `pip install dist/*.whl` works | installable |
| 0.7 | **Update design docs** | development, cli-reference, README | docs reflect the ported layout |

**Tests required:** config precedence + validation (valid/invalid/fail-closed, F7); CLI smoke; coverage gate.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `make setup` works on a clean machine; `agentwatch --help` lists subcommands
- [ ] Bad config **fails closed** (F7); CI green

**Design docs to update:** [development.md](../../development.md), [cli-reference.md](../../reference/cli-reference.md),
[README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M1 — Record format + security-event schema

**Goal:** the normative record and security-event models — **ported** from the shipped trace schema and
extended with the agentwatch security-event schema.

**Requirements / PRDs:** R1, R5, [PRD 15](../../prd/15-data-model.md),
[record-format spec](../../reference/record-format-spec.md), [`schema/`](../../../schema/).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 1.1 | **Port** record/trace schema + span models from `agent-exec-trace` | record model | fields match [`agent-record.schema.json`](../../../schema/agent-record.schema.json) |
| 1.2 | Extend with **security-event schema** (new) | event model | enum: `denied`…`halted` |
| 1.3 | Validation entry point | `validate_record()` / `validate_event()` | invalid rejected, not coerced (F8) |
| 1.4 | Version handling | `schema_version` / `event_version` checks | unknown version rejected clearly |
| 1.5 | Fixtures | sample valid + invalid records/events | used by tests + conformance |
| 1.6 | **Update design docs** | record-format design/spec, data-dictionary | docs match models |

**Tests required:** JSON round-trip; invalid rejected (F8); event enum + version enforcement; ported-schema
compatibility with the shipped model.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Record + event schemas validate; round-trip green
- [ ] Invalid records rejected (F8); schema version enforced

**Design docs to update:** [record-format-spec.md](../../reference/record-format-spec.md),
[record-format-spec.md](../../reference/record-format-spec.md), [data-dictionary.md](../../design/data-dictionary.md),
[PRD 15](../../prd/15-data-model.md), [`schema/README.md`](../../../schema/README.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 1 green ⇒ proceed to [Part 2 (M2–M3)](wbs-v0.1.0-part2-recording.md).
