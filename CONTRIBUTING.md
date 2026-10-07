# Contributing to agentwatch

Thanks for helping. The harness landscape moves faster than any one team, so the most valuable contributions
are **adapters and readers that make agentwatch work with *your* stack**. This guide covers the "works with X"
paths and the rules every contribution must clear.

By contributing you agree to the [DCO](https://developercertificate.org/): sign commits with `git commit -s`.

## Set up & run the gates

Follow the [development guide](docs/development.md). The gates that must be green locally:

```sh
make setup
make lint        # ruff — zero violations
make typecheck   # mypy --strict — clean
make test        # pytest — green, coverage >= 95% + the repo guard
make web-test    # vitest + axe (if you touched apps/web)
```

CI runs exactly these. A PR that skips a gate will not land.

## "Works with X" — the contribution paths

### 1. Add a harness adapter

Implement the published [adapter plugin contract](docs/reference/adapter-api.md): a small module that maps
native harness events to agentwatch records.

- Declare `HARNESS_ID`, `CAPABILITIES`, and `DOCUMENTED_GAPS` (disjoint). A gap you do not implement must be
  **declared**, never dropped silently (R3).
- `normalize(message) -> list[AgentRecord]`; unknown phases raise your adapter error class.
- Register an `AdapterSpec` and ship a **populated** conformance pack (fixtures with `message` + `expected`).
  `conformance.assert_registered_conform()` blocks CI otherwise (O1).
- The plugin contract is a **semver extension surface**: additive in a minor, breaking only in a major with a
  deprecation cycle (see the
  [backwards-compatibility policy](docs/reference/backwards-compatibility-policy.md)).

### 2. Add a detector

See [tutorials/04-write-a-detector.md](docs/tutorials/04-write-a-detector.md). Register the detector, add a
corpus case, and regenerate the catalog (`python scripts/generate_detector_catalog.py`). A detector that fires
on nothing fails the non-silent gate.

### 3. Add a native log reader

The LOG-1 reader tier is designed for community contribution: a pinned OSS parser maps a harness's native
trace files to records. Pin the upstream commit in the workflow and in `THIRD_PARTY_NOTICES.md`.

## Redaction & fixture rules (non-negotiable)

agentwatch never persists secrets, and contributions must not either.

- **Fixtures are synthetic or redaction-verified.** Never commit real credentials, tokens, customer content, or
  PII. Build fixtures from public formats or the redaction attack pack.
- Run the redaction self-test and the security scan before you push:

  ```sh
  make security-scan    # gitleaks + trufflehog + pip-audit + egress audit
  ```

- A fixture that contains a live secret fails CI; fix the fixture, do not add an allowlist entry.

## Legacy import name

New code imports `agentwatch`. If you are migrating an older codebase that imports `agent_exec_trace`, run the
codemod:

```sh
python scripts/codemod_agent_exec_trace.py path/to/src
python scripts/codemod_agent_exec_trace.py --check path/to/src   # CI-safe dry run
```

The legacy import path keeps working through a compatibility shim (DD-12); the codemod is the supported way to
move off it.

## Docs & governance

- Update the relevant design/reference doc and link it from the WBS.
- If you make a **public claim**, add it to `docs/release/claims-ledger.json` with live evidence (a test, file,
  script, workflow, or doc) and run `python scripts/check_claims.py --write`.
- Architecture decisions get an ADR under [docs/adr/](docs/adr/README.md).
