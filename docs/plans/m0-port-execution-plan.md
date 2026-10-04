# agentwatch M0 — Port Execution Plan

**Spec:** [WBS M0](../wbs/v0.1.0/wbs-v0.1.0-part1-port-foundation.md#milestone-m0--port-the-entire-codebase) ·
[PRD 10](../prd/10-feature-parity.md) (parity) · [PRD 03](../prd/03-landscape.md) · issues #3–#9, #113, #114.

**Source:** `agent-exec-trace` (MIT), local clone at `../_port-src`, HEAD `008e1c7eeed9de74044e8065e1be241bfee20704`,
75 commits, Python ≥3.10, Node 20.

## Decisions (from your human partner)

- **Workspace:** in place on `feat-v0.1.0` (no worktree).
- **History:** **single import commit**; provenance recorded in `THIRD_PARTY_NOTICES.md` + `CHANGELOG.md`
  (no `filter-repo`, no subtree). Ruling D2 below.

## Global Constraints

- **Do not clobber** agentwatch's own `docs/` (PRDs/design/reference), `schema/`, `.github/` — they are ahead
  of the source. Port the source **code + tooling**, plus only the non-colliding source docs subset.
- **DD-12 compat shim is binding:** the `agent_exec_trace` import path stays in exactly **one** shim module
  plus the migration guide. "Zero `agent_exec_trace` references" means zero **except that allowlist**.
- **Exit gate:** ported suite green; coverage ≥ 95%; `ruff` zero; `mypy --strict` clean.
- **Commits:** conventional commits, signed off (`git commit -s`, DCO).

## Interfaces / shared surfaces

- Task 1 places the tree; Tasks 2–6 edit that same tree. No cross-task interface beyond the file layout.
- Task 5's guard test depends on Task 2's allowlist definition.

---

## Task 1 — Import the source tree + record provenance (0.1, 0.3, 0.6)

**Deliverable:** the `agent-exec-trace` code/tooling tree present at the agentwatch root; MIT provenance
recorded for source repo + commit + date.

**Steps**

1. Copy from `../_port-src` into the repo root, excluding git/VCS and the agentwatch-owned dirs:
   `packages/ services/ apps/ deploy/ examples/ tests/ scripts/ Makefile pyproject.toml docker-compose.yml
   .pre-commit-config.yaml .python-version .node-version .gitignore` **merged**, and the non-colliding docs
   subset (`docs/architecture/ docs/guides/ docs/assets/ docs/fixtures/ docs/real-agent-integration/ docs/test/
   docs/examples.md`). Skip `.github/`, `docs/design docs/reference docs/field-test docs/wbs`, `schema/`,
   and top-level README/CHANGELOG/LICENSE/SECURITY (agentwatch owns these).
   - Do **not** run `pip install` yet.
2. Record provenance in `THIRD_PARTY_NOTICES.md`: source URL, commit SHA, import date, MIT license
   (extend the existing `agent-exec-trace (AgentObservatory)` section).
3. Add a `CHANGELOG.md` `[Unreleased]` entry naming the imported tree + SHA.
4. `git add -A && git commit -s` — message `chore(port): import agent-exec-trace codebase (M0).

**Expected**

- `git ls-files` contains `Makefile`, root `pyproject.toml`, `packages/python-sdk/`, `services/api/`,
  `services/analytics/`, `apps/web/`, `deploy/`, `examples/`, `scripts/`.
- `git status` clean; `THIRD_PARTY_NOTICES.md` includes the SHA.

---

## Task 2 — Rename namespace `agent_exec_trace` → `agentwatch` (0.2)

**Deliverable:** package directory + all imports/configs/docs renamed; compat shim retained.

**Steps**

1. `git mv packages/python-sdk/src/agent_exec_trace packages/python-sdk/src/agentwatch`.
2. Rename every `agent_exec_trace` reference to `agentwatch` across code, tests, configs, and the ported
   docs subset — **except** the DD-12 shim.
3. Create the compat shim module that keeps `import agent_exec_trace` working (re-exports from `agentwatch`).
4. Run a repo-wide grep; the only hits are the shim + migration docs (allowlist).
5. Commit.

**Expected**

- `packages/python-sdk/src/agentwatch/` exists; no `agent_exec_trace` package dir.
- The allowlist in Task 5 passes; grep shows only shim + migration guide.

---

## Task 3 — Adapt packaging metadata (0.4)

**Deliverable:** packaging metadata rebranded; `pip install -e packages/python-sdk` works.

**Steps**

1. Update each package `pyproject.toml` `name`/description/URLs: `agent-exec-trace*` → `agentwatch*`.
2. Wire the `agentwatch` console script (CLI entry point) if the source exposes one.
3. `python3 -m pip install -e packages/python-sdk` (and api/analytics as needed).
4. Commit.

**Expected**

- editable install succeeds; `python3 -c "import agentwatch"` works (after Task 2).
- No `agent-exec-trace` distribution name remains.

---

## Task 4 — Get the ported test suite green (0.5)

**Deliverable:** the imported Python test suite passes (minimal adaptation only).

**Steps**

1. Install dev deps for the three packages (sdk, api, analytics).
2. Run the ported suite per `Makefile test` (pytest per package).
3. Fix only import/namespace/packaging breakage — **no behavior changes**. Anything else → ledger ruling.
4. Re-run to green.
5. Commit.

**Expected**

- `pytest packages/python-sdk services/api services/analytics` → all pass.
- Failures are only rename-induced and are fixed without changing behavior.

---

## Task 5 — Guard test: no stray `agent_exec_trace` references (0.T)

**Deliverable:** a test that fails if any `agent_exec_trace` reference remains outside the allowlist.

**Steps**

1. **RED:** write `tests/test_no_legacy_namespace.py` scanning tracked text files for `agent_exec_trace`,
   allowlisting the compat shim + migration guide. Run it against a deliberately un-allowlisted reference to
   watch it fail, then confirm it passes on the clean tree.
2. **GREEN:** wire the allowlist so the guard passes on the ported tree.
3. Commit.

**Expected**

- Guard test fails when a stray reference is introduced; passes on the clean tree.

---

## Task 6 — Update design docs (0.7, 0.D)

**Deliverable:** `docs/development.md`, `docs/design/architecture-tour.md`, `THIRD_PARTY_NOTICES.md`,
`CHANGELOG.md` describe the ported tree; WBS index notes M0 done.

**Steps**

1. Describe the ported monorepo layout (`packages/`, `services/`, `apps/`, `deploy/`, `examples/`).
2. Update `THIRD_PARTY_NOTICES`/`CHANGELOG` porting notes.
3. Link the ported tree from the WBS index + this plan.
4. Commit.

**Expected**

- Docs reference real paths that exist; `docs/development.md` describes `make setup/lint/test`.

---

## Rulings (recorded here so they survive compaction)

- **D1 — Docs collisions:** keep agentwatch's `docs/{design,reference,field-test,wbs}`, `schema/`, `.github/`;
  port only the non-colliding source docs subset. *Why:* agentwatch docs are the normative, newer set.
  *Cost if wrong:* a source doc is missing and must be recovered from `_port-src`.
- **D2 — History:** single import commit with recorded SHA instead of filter-repo/subtree. *Why:* partner's
  explicit choice. *Cost if wrong:* no line-level blame across the port boundary (provenance still recorded).
- **D3 — Namespace vs DD-12:** the "zero `agent_exec_trace` references" acceptance is read as "zero outside
  the compat shim + migration docs", because [PRD 10 §D](../prd/10-feature-parity.md) and DD-12 require the
  old import path to keep working. *Cost if wrong:* the guard test over/under-scopes by two files.
