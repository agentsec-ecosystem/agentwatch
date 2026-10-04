# agentwatch M1 — Foundation & identity Execution Plan

**Spec:** [WBS M1](../wbs/v0.1.0/wbs-v0.1.0-part1-port-foundation.md#milestone-m1--foundation--identity) ·
[PRD 16 — Configuration](../prd/16-configuration.md) · [PRD 02 — Architecture §CLI](../prd/02-architecture.md) ·
[cli-reference](../reference/cli-reference.md) · issues #10–#15, #115, #116.

**Context:** M0 (bulk port) is complete on `feat-v0.1.0`. The ported tree has the SDK, analytics, API, and web
UI, but **no CLI and no layered config loader** — the source repo exposed none. M1 adds the identity,
CLI, configuration, CI, and packaging foundation.

## Decisions (rulings taken at planning time)

- **D1 — CLI home:** the `agentwatch` CLI lives in the existing `agentwatch` distribution
  (`packages/python-sdk/src/agentwatch/cli/`), exposed as console script `agentwatch`. *Why:* the docs
  publish the core as `pip install agentwatch` ([upgrade runbook](../runbooks/upgrade-and-rollback.md)); one
  distribution named `agentwatch` cannot be duplicated. *Cost if wrong:* move the module + one entry point.
- **D2 — CLI framework:** stdlib `argparse`. *Why:* the SDK package is the dependency-light core and currently
  has no CLI dependency; `click` would add a runtime dep for a convenience. *Cost if wrong:* mechanical port.
- **D3 — Config module:** new `agentwatch/configuration.py` for the PRD 16 operator config, distinct from the
  existing SDK runtime `agentwatch/config.py` (`SDKConfig`). *Why:* PRD 16 governs the daemon/CLI, not span
  instrumentation. *Cost if wrong:* rename to avoid confusion; no behavior impact.
- **D4 — Python 3.10 support:** use `tomllib` on 3.11+ and the `tomli` backport on 3.10
  (`requires-python = ">=3.10"`). *Cost if wrong:* one import swap.
- **D5 — M1 subcommand depth:** register every documented subcommand; `status` and config plumbing are fully
  implemented. Subcommands whose real behavior belongs to later milestones (`init`, `sessions`, `replay`,
  `export`, `verify-store`, `migrate`, `uninstall`) are present and **fail closed** with a clear
  "not implemented in v0.1.0 M1" message and non-zero exit. *Why:* M1's acceptance is "`agentwatch --help`
  lists commands"; the daemon/store/hooks land in M3–M5. *Cost if wrong:* a stub is replaced by real logic.
- **D6 — Workspace:** in place on `feat-v0.1.0`, no worktree (matches the M0 partner decision).

## Global Constraints

- **Exit gate:** `make lint` (ruff zero), `make typecheck` (mypy --strict clean), `make test`
  (green, coverage ≥95%), plus the repo guard test.
- **Fail closed:** invalid/unknown config refuses to start (F7); no silent fallback.
- **Commits:** conventional commits, signed off (`git commit -s`, DCO).
- **No new runtime dependency** except `tomli` (py<3.11 only).

## Interfaces / shared surfaces

- Task 2 defines `agentwatch.configuration`: `load_config`, `AgentwatchConfig`, `ConfigError`, precedence.
  Task 3's CLI imports `load_config` + `ConfigError` for `status`/global flags.
- Task 1 defines the console-script entry point (`agentwatch.cli:main`) that Task 3 fills in.
- Task 5 builds the artifacts Task 1's metadata configures.

---

## Task 1 — Packaging identity + quality gates (1.1 / #10)

**Deliverable:** `agentwatch` build metadata with a working `agentwatch` console-script entry point; build
config; quality-gate tooling verified.

**Steps**

1. In `packages/python-sdk/pyproject.toml`: keep `name = "agentwatch"`; add
   `[project.scripts] agentwatch = "agentwatch.cli:main"`; add `tomli>=2; python_version < '3.11'` to
   `dependencies`; add `build>=1.2` to the `dev` extra.
2. **RED:** add `packages/python-sdk/tests/test_packaging_metadata.py` asserting the built metadata exposes
   distribution `agentwatch`, console script `agentwatch -> agentwatch.cli:main`, and the `tomli` marker.
   Run it; the entry-point assertion fails before step 1's scripts table exists (verify by reading it).
3. **GREEN:** apply step 1.
4. Run `make lint` for the sdk package; run the new test.
5. Commit (`git commit -s`): `chore(packaging): expose agentwatch console script and build metadata (M1)`.

**Expected**

- `python3 -c "import tomllib; ..."` metadata test passes; the console-script table is present.
- `ruff check packages/python-sdk` → zero violations.

---

## Task 2 — Configuration loader + validation (1.3 / #12)

**Deliverable:** `agentwatch/configuration.py` implementing PRD 16: layered precedence, documented defaults,
strict unknown-key rejection, and fail-closed errors.

**Steps**

1. **RED:** write `packages/python-sdk/tests/test_configuration.py` covering:
   - defaults match PRD 16 (`harness=claude-code`, `mode=monitor`, `store.path=~/.local/share/agentwatch`,
     `store.retention_days=30`, `store.max_size_mb=1024`, `privacy.mode=metadata-only`,
     `redaction.self_test=enabled`, `export.enabled=false`, `export.format=otel-genai`,
     `health.endpoint=127.0.0.1:9100`, `log.level=info`);
   - precedence low→high: system < user < project < env (`AGENTWATCH_*`) < CLI overrides;
   - objects merge recursively, arrays replace;
   - unknown key rejected with `ConfigError`;
   - bad value type/enum rejected with `ConfigError`;
   - `export.enabled=true` without `export.otlp_endpoint` rejected (fail closed);
   - `load_config` raises `ConfigError` and never returns a partial config.
2. Run the tests; they fail (module missing) — the expected RED.
3. **GREEN:** implement `configuration.py`:
   - `ConfigError(Exception)`;
   - `AgentwatchConfig` (frozen dataclass or validated mapping) with nested `store`, `privacy`, `redaction`,
     `export`, `health`, `log` sections;
   - `load_config(*, paths=None, env=None, cli_overrides=None) -> AgentwatchConfig` with default
     locations, deep merge, strict unknown keys, enum/type validation, and the export self-test rule.
4. Re-run tests; run the full sdk suite + coverage.
5. Commit: `feat(config): layered fail-closed configuration loader (M1)`.

**Expected**

- `pytest packages/python-sdk --cov --cov-fail-under=95` green.
- An unknown key or invalid value raises `ConfigError` (watched in RED).

---

## Task 3 — CLI framework + subcommands (1.2 / #11)

**Deliverable:** `agentwatch.cli` wired with every documented subcommand; `agentwatch --help` lists them.

**Steps**

1. **RED:** write `packages/python-sdk/tests/test_cli.py`:
   - `agentwatch --help` exits 0 and lists `init`, `status`, `sessions`, `replay`, `export`, `verify-store`,
     `migrate`, `uninstall`;
   - each subcommand's `--help` exits 0;
   - `status` prints the resolved config summary and exits 0;
   - an invalid config path makes a command exit non-zero via the fail-closed path (F7);
   - unknown subcommand exits non-zero.
2. Run; fail (module missing).
3. **GREEN:** implement `agentwatch/cli/__init__.py` + `agentwatch/cli/main.py`:
   - `main(argv=None) -> int` building an `argparse` parser, returning process exit codes;
   - global `--config` / `--set key=value` overrides threaded into `load_config`;
   - `status` implemented; the milestone-deferred subcommands fail closed (D5);
   - `agentwatch/cli/__main__.py` so `python -m agentwatch.cli` works.
4. Re-run tests; append `[project.scripts]` already added in Task 1.
5. Commit: `feat(cli): agentwatch argparse CLI with all subcommands (M1)`.

**Expected**

- `python -m agentwatch --help` lists all eight subcommands.
- CLI test suite green; coverage ≥95%.

---

## Task 4 — CI (1.4 / #13)

**Deliverable:** `.github/workflows/ci.yml` runs ruff, mypy --strict, and pytest with the coverage gate across
the three packages plus the repo guard; DCO already present.

**Steps**

1. Replace the placeholder `ci.yml` with a real workflow: checkout, setup-python (3.10 + 3.12 matrix),
   `pip install -e` each package with `[dev]`, `make lint`, `make typecheck`, `make test`.
2. Add `packages/python-sdk/tests/test_ci_workflow.py` asserting `ci.yml` contains no placeholder text and
   references `ruff`/`mypy`/`pytest` (guards against regression to the starter file).
3. Validate the YAML parses; run `make lint`, `make typecheck`, `make test` locally to confirm the commands CI
   will run.
4. Commit: `ci: real lint/typecheck/test workflow with coverage gate (M1)`.

**Expected**

- Local `make lint`, `make typecheck`, `make test` all exit 0.
- Workflow YAML parses and names all three gates.

---

## Task 5 — Packaging: wheel + sdist + npx launcher (1.5 / #14)

**Deliverable:** `python -m build` produces wheel + sdist exposing the `agentwatch` console script; the
`@agentsec-ecosystem/cli` Node launcher shells to it.

**Steps**

1. Build the sdk: `python -m build --no-isolation packages/python-sdk` → wheel + sdist in `dist/`.
2. Verify the wheel installs in a throwaway venv and `agentwatch --help` works (or, if offline, verify the
   wheel entry point via `unzip -p <wheel> '*/entry_points.txt'`).
3. **RED:** add `packages/python-sdk/tests/test_dist_artifacts.py` (skipped when artifacts absent) asserting a
   built wheel declares the `agentwatch` console script.
4. Create `packages/cli/` (`@agentsec-ecosystem/cli`): `package.json` with `bin.agentwatch` and a
   `bin/agentwatch.js` that spawns `python3 -m agentwatch.cli` passing argv, forwarding exit code.
5. Commit: `build(packaging): wheel+sdist and @agentsec-ecosystem/cli launcher (M1)`.

**Expected**

- Wheel + sdist exist under `dist/`; wheel metadata exposes `agentwatch = agentwatch.cli:main`.
- `node packages/cli/bin/agentwatch.js --help` prints the CLI help (python3 available).

---

## Task 6 — Docs (1.6 + 1.D / #15, #116)

**Deliverable:** `docs/development.md`, `docs/reference/cli-reference.md`, `README.md`, `CHANGELOG.md`, and
the WBS index describe the real M1 identity/CLI/config/CI.

**Steps**

1. Update `cli-reference.md` with usage, global flags, config precedence, and the M1 implementation status.
2. Update `development.md` with CLI/config/CI/quality-gate notes and the `packages/cli` launcher.
3. Update `README.md` quickstart (`agentwatch --help`, config) and `CHANGELOG.md` `[Unreleased]` M1 entry.
4. Add a repo-level link-check test `tests/test_docs_links.py` that walks `docs/` + `README.md` relative links
   and fails on a missing target (issue #116's link-check acceptance).
5. Mark M1 in the WBS index/part file as shipped.
6. Commit: `docs(m1): document identity, CLI, config, and CI (M1)`.

**Expected**

- Link-check test green; docs reference existing paths.
- CHANGELOG + WBS note M1.

---

## Rulings (recorded here so they survive compaction)

- **D1** CLI in the `agentwatch` distribution · **D2** argparse · **D3** `configuration.py` separate from
  `SDKConfig` · **D4** tomllib/tomli split · **D5** stub milestone-deferred subcommands fail closed ·
  **D6** in-place on `feat-v0.1.0`.
