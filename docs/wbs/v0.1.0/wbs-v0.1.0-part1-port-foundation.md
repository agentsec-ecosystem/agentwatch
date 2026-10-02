# WBS v0.1.0 — Part 1: Port the Codebase & Foundation (M0–M1)

**BLUF:** **M0 is a bulk port of the entire `agent-exec-trace` codebase** (urgent — it makes agentwatch
self-contained; the old repo is retained and made private, never deleted). M1 rebrands/adapts the foundation.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M0 — Port the entire codebase

**Goal:** move **all** of `agent-exec-trace` into agentwatch, rename the namespace, and get the ported test
suite green — after which the source repository is **retained and made private** (never deleted).

**Requirements / PRDs:** [PRD 10](../../prd/10-feature-parity.md) (parity is mandatory and in-repo),
[THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md).

**Work items (this milestone *is* the port)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 0.1 | **Port** the entire repo tree (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, `Makefile`, `pyproject.toml`, docs subset) | full tree present | tree mirrors the source | #3 |
| 0.2 | **Rename namespace** `agent_exec_trace` → `agentwatch` across code, tests, configs, docs | renamed | zero `agent_exec_trace` references remain | #4 |
| 0.3 | **Preserve git history** (`git filter-repo` / subtree merge) | merged history | provenance intact | #5 |
| 0.4 | Adapt packaging metadata to `agentwatch` | packaging | `pip install -e .` works | #6 |
| 0.5 | Get the **ported test suite green** (minimal adaptation only) | passing tests | ported suite passes | #7 |
| 0.6 | Record provenance + porting notes | `THIRD_PARTY_NOTICES`, `CHANGELOG` | MIT attribution recorded | #8 |
| 0.7 | **Update design docs** | architecture-tour, development, THIRD_PARTY_NOTICES | docs describe the ported tree | #9 |
| 0.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #113 |
| 0.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #114 |

**Tests required:** the entire ported suite (SDK, analytics, API, UI, E2E) passes after the namespace rename.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] The full `agent-exec-trace` codebase is represented in agentwatch
- [ ] Zero `agent_exec_trace` references remain; history preserved
- [ ] Ported suite green → **`agent-exec-trace` is retained and made private (not deleted)**

**Design docs to update:** [architecture-tour.md](../../design/architecture-tour.md),
[development.md](../../development.md), [THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md),
[CHANGELOG](../../../CHANGELOG.md), [README](../../../README.md).

---

## Milestone M1 — Foundation & identity

**Status:** ✅ **shipped** — execution plan: [m1-foundation-execution-plan.md](../../plans/m1-foundation-execution-plan.md);
issues #10–#15, #115, #116.

**Goal:** agentwatch identity, CLI, config, packaging, and CI — **ported** from the source tooling and
rebranded.

**Requirements / PRDs:** NFR-11, [PRD 16](../../prd/16-configuration.md),
[development guide](../../development.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 1.1 | **Port** pyproject/quality-gate tooling + rebrand metadata | `agentwatch` build config | name/bin = agentwatch | #10 |
| 1.2 | **Port** CLI framework + install pattern; wire all subcommands | [cli-reference](../../reference/cli-reference.md) | `agentwatch --help` lists commands | #11 |
| 1.3 | Config loader + validation (precedence, strict, **fail-closed**) | [PRD 16](../../prd/16-configuration.md) | invalid config refuses to start (F7) | #12 |
| 1.4 | CI (ruff, mypy, pytest, **coverage ≥95%**, DCO) | GitHub Actions | CI green on PR | #13 |
| 1.5 | Packaging: wheel + sdist + `@agentsec-ecosystem/cli` launcher | artifacts | installable | #14 |
| 1.6 | **Update design docs** | development, cli-reference, README | docs match identity | #15 |
| 1.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #115 |
| 1.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #116 |

**Tests required:** config precedence + validation (F7); CLI smoke.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `make setup`/`lint`/`test` work; `agentwatch --help` lists subcommands
- [ ] Bad config fails closed (F7); CI green

**Design docs to update:** [development.md](../../development.md), [cli-reference.md](../../reference/cli-reference.md),
[README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 1 green ⇒ agentwatch is self-contained (the predecessor is retained privately); proceed to [Part 2 (M2–M3)](wbs-v0.1.0-part2-schema-adapter.md).
