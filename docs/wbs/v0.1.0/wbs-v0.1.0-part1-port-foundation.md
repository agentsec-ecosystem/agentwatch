# WBS v0.1.0 — Part 1: Port the Codebase & Foundation (M0–M1)

**BLUF:** **M0 is a bulk port of the entire `agent-exec-trace` codebase** (urgent — it makes the old repo
redundant so it can be deleted). M1 rebrands/adapts the foundation.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M0 — Port the entire codebase

**Goal:** move **all** of `agent-exec-trace` into agentwatch, rename the namespace, and get the ported test
suite green — at which point the source repository is **redundant and can be deleted**.

**Requirements / PRDs:** [PRD 10](../../prd/10-feature-parity.md) (parity is mandatory and in-repo),
[THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md).

**Work items (this milestone *is* the port)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 0.1 | **Port** the entire repo tree (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`, `tests/`, `schema`, `Makefile`, `pyproject.toml`, docs subset) | full tree present | tree mirrors the source |
| 0.2 | **Rename namespace** `agent_exec_trace` → `agentwatch` across code, tests, configs, docs | renamed | zero `agent_exec_trace` references remain |
| 0.3 | **Preserve git history** (`git filter-repo` / subtree merge) | merged history | provenance intact |
| 0.4 | Adapt packaging metadata to `agentwatch` | packaging | `pip install -e .` works |
| 0.5 | Get the **ported test suite green** (minimal adaptation only) | passing tests | ported suite passes |
| 0.6 | Record provenance + porting notes | `THIRD_PARTY_NOTICES`, `CHANGELOG` | MIT attribution recorded |
| 0.7 | **Update design docs** | architecture-tour, development, THIRD_PARTY_NOTICES | docs describe the ported tree |

**Tests required:** the entire ported suite (SDK, analytics, API, UI, E2E) passes after the namespace rename.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] The full `agent-exec-trace` codebase is represented in agentwatch
- [ ] Zero `agent_exec_trace` references remain; history preserved
- [ ] Ported suite green → **`agent-exec-trace` is redundant and may be deleted**

**Design docs to update:** [architecture-tour.md](../../design/architecture-tour.md),
[development.md](../../development.md), [THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md),
[CHANGELOG](../../../CHANGELOG.md), [README](../../../README.md).

---

## Milestone M1 — Foundation & identity

**Goal:** agentwatch identity, CLI, config, packaging, and CI — **ported** from the source tooling and
rebranded.

**Requirements / PRDs:** NFR-11, [PRD 16](../../prd/16-configuration.md),
[development guide](../../development.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 1.1 | **Port** pyproject/quality-gate tooling + rebrand metadata | `agentwatch` build config | name/bin = agentwatch |
| 1.2 | **Port** CLI framework + install pattern; wire all subcommands | [cli-reference](../../reference/cli-reference.md) | `agentwatch --help` lists commands |
| 1.3 | Config loader + validation (precedence, strict, **fail-closed**) | [PRD 16](../../prd/16-configuration.md) | invalid config refuses to start (F7) |
| 1.4 | CI (ruff, mypy, pytest, **coverage ≥95%**, DCO) | GitHub Actions | CI green on PR |
| 1.5 | Packaging: wheel + sdist + `@agentsec-ecosystem/cli` launcher | artifacts | installable |
| 1.6 | **Update design docs** | development, cli-reference, README | docs match identity |

**Tests required:** config precedence + validation (F7); CLI smoke.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `make setup`/`lint`/`test` work; `agentwatch --help` lists subcommands
- [ ] Bad config fails closed (F7); CI green

**Design docs to update:** [development.md](../../development.md), [cli-reference.md](../../reference/cli-reference.md),
[README](../../../README.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 1 green ⇒ the old repo is redundant; proceed to [Part 2 (M2–M3)](wbs-v0.1.0-part2-schema-adapter.md).
