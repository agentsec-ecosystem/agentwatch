# M14 — Engineering Rigor (Q1–Q13) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the engineering floor so the product's claims are *measured*: property/differential
redaction testing, mutation and fuzz testing on the trust path, whole-repo CI, an enforced performance
budget, published conformance vectors, a forward-compatibility matrix, a machine-readable error
contract, a claims ledger, executable docs, an accessibility conformance level, time correctness, and
a release pipeline that signs what it ships.

**Architecture:** Test/CI/tooling work. It adds no product surface except where a claim needs a
command (`agentwatch verify-release`, Q13) and the error envelope (Q8). A shared `tests/_hypothesis`
strategy module and a `scripts/` gate harness keep the property/mutation/fuzz/perf jobs thin.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `hypothesis` (new dev dep); `mutmut`
(new dev dep, Q2); `atheris`/`hypothesis` (Q3); `ruff`; `mypy --strict`; GitHub Actions.

**Spec:** PRD [38](../prd/38-engineering-rigor.md) · WBS
[Part 9](../wbs/v0.1.0/wbs-v0.1.0-part9-rigor-and-evidence.md) · issues #218–#230.

## Global Constraints

- Fail closed, never silent (PRD 17); redaction before storage (DD-06); no egress by default (NFR-9).
- Test-only additions must not change the record/store schema (`0.1.0`) or the runtime dependency set;
  new dev dependencies are recorded per NFR-5 (PRD 38 / `docs/reference/tech-stack.md`).
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.
- CI jobs that need Docker skip with a clear reason, never silently pass.

## Review Focus

1. A fixed corpus measures regression, not recall — the property/differential test must fail on a
   seeded unredacted secret shape, not merely pass the known corpus.
2. Every gate fails on a *deliberate* break (a slowdown, a survivor over budget, an unsigned artifact),
   verified by a seeded-negative test.
3. Generated artifacts (exit-code table, perf number, vectors, ledger) are generated from code/CI, not
   hand-maintained prose.

---

## Tasks

### Task 1 — Q1 (#218): Property-based + differential redaction testing
- [x] Create `tests/test_redaction_properties.py` with `hypothesis` strategies (key prefixes, base64url
      bodies, JWT triplets, connection strings) under mutation (whitespace, encoding, chunking, unicode
      confusables); assert no plaintext survives `redact_mapping` + `RedactionConfig.apply`.
- [x] Differential oracle: run the corpus through pinned `gitleaks`/`detect-secrets`-style rule
      signatures and report any agentwatch-missed rule class as a failure (not a silent pass).
      Pinned in `tests/_secret_oracle.py`; `EXPECTED_GAPS` is the explicit non-claim list.
- [x] Add `hypothesis` to `packages/python-sdk[dev]`; record the decision in
      `docs/reference/tech-stack.md`.
- [x] Seeded-negative check proves the property test fails on an unredacted shape.

### Task 2 — Q2 (#219): Mutation testing on the trust path
- [x] Add `mutmut` (or `cosmic-ray`) dev dep + config scoped to `chain/store`, `redact`, `validate_*`.
      `cosmic-ray` is an optional `[mutation]` extra + `scripts/cosmic_ray.toml` for deep runs; its
      filter/DB layer is unstable on the supported Python, so the enforced gate is a deterministic,
      curated harness.
- [x] `scripts/mutation_gate.py` with a surviving-mutant budget + documented allow-list.
- [x] CI job fails when survivors exceed the budget; seeded-negative test proves the gate fails
      (`--self-test` + `tests/test_mutation_gate.py`).

### Task 3 — Q3 (#220): Fuzzing the parsers
- [x] `hypothesis` harnesses for hook JSON, socket frames, store lines, transcripts, NDJSON/OTel ingest,
      and MCP JSON-RPC in `tests/test_fuzz_parsers.py`; bounded wall time; committed `@example` seed
      corpus. (`atheris` is not installed; `hypothesis` is the documented fallback.)
- [x] A seeded malformed input is contained (rejected/quarantined/empty), never a crash. The fuzzer found
      a real `TypeError` in `session_export.parse_ndjson` on a JSON scalar; fixed to fail closed and the
      minimized input `"0"` is committed as a regression.
- [x] Nightly CI job `.github/workflows/fuzz.yml` runs each harness at 1000 examples.

### Task 4 — Q4 (#221): Enforce the performance budget in CI
- [x] `pytest-benchmark` (or reuse `perf.time_call`) job with a committed baseline + p99 gate +
      documented tolerance band; published number generated from the run.
      `scripts/perf_gate.py` + `perf/baseline.json` + generated `docs/reference/performance.md`;
      tolerance = 3.0× above a 2.0 ms floor, absolute NFR cap 5 ms.
- [x] Seeded-negative test: a deliberate slowdown fails the gate (`--self-test` + `tests/test_perf_gate.py`).

### Task 5 — Q5 (#222): Make CI run the whole repo
- [x] Add web unit + axe jobs (`.github/workflows/web.yml`), Playwright E2E against the compose stack
      (`.github/workflows/e2e.yml`), no-network E2E (`.github/workflows/offline-e2e.yml`, M12), and a
      docker-stack smoke test (`.github/workflows/stack-smoke.yml`). Shared runners in
      `scripts/run-e2e.sh` / `scripts/stack-smoke.sh`.
- [x] Required vs informational jobs documented (`docs/development.md`); Docker-less runs skip with a
      clear reason (`run-e2e.sh` / `stack-smoke.sh` preflight), never silently pass.

### Task 6 — Q6 (#223): Conformance test vectors for the store and chain
- [x] `schema/vectors/store/` with valid/tampered/tombstoned/purged/gap/checkpoint (+ unsupported-format)
      cases and `expected-verdicts.json`; built by `scripts/generate_store_vectors.py`.
- [x] Both `store.py` (`RecordStore.verify`) and the standalone, dependency-free
      `schema/vectors/verify_store.py` match the table in CI
      (`tests/test_store_vectors.py`). The standalone verifier is the reference the M15 **S12**
      deliverable (#232) formalizes; #232 stays open.

### Task 7 — Q7 (#224): Forward-compatibility test matrix
- [x] Commit a frozen store per released format version + the pre-marker legacy shape under
      `tests/fixtures/store-versions/` (`manifest.json`); CI asserts read/verify/replay/export for each
      supported one and fail-closed for an unknown format (`tests/test_forward_compat.py`).

### Task 8 — Q8 (#225): One machine-readable error contract
- [x] One envelope `{"error": {"code","message","hint","doc_url"}}` in `agentwatch.errors`; the exit-code
      table in `docs/reference/errors.md` is *generated* from the catalog and checked in CI.
      `tests/test_error_contract.py` asserts every subcommand's failure path emits it, plus the
      specific codes (`E_CONFIG`, `E_NOT_IMPLEMENTED`, `E_CHAIN_BROKEN`, `E_SESSION_NOT_FOUND`), and
      that success emits none.

### Task 9 — Q9 (#226): A claims ledger
- [x] `docs/release/claims-ledger.md` + `claims-ledger.json`: each public claim → exact wording → source →
      live evidence links → last verified. `scripts/check_claims.py` fails a claim with no evidence, a
      renamed test (AST check), or a deleted file, and fails if the generated table drifts; wired in
      `.github/workflows/claims.yml` with a `--self-test`.

### Task 10 — Q10 (#227): Executable documentation
- [x] The J3 investigation cookbook's `run`-annotated blocks execute offline against the synthetic seed
      dataset, in CI (`.github/workflows/docs.yml`, `scripts/check_docs_commands.py`); a broken command —
      or an illustrative/`service` block that gets executed — fails. Scope note: install/network/service
      tutorials stay link-checked and compose-covered (Q5).

### Task 11 — Q11 (#228): Accessibility conformance level
- [x] Target WCAG 2.2 AA stated in `docs/reference/accessibility.md` with a VPAT-lite per view; axe in CI
      (unit + Playwright), a Playwright contrast check, and a keyboard-only E2E journey through CUJ-8's
      operator UI. Contrast/heading-order fixes the check surfaced landed in the web app.

### Task 12 — Q12 (#229): Time correctness as a tested property
- [x] Property-test `since_cutoff` and hour bucketing across DST boundaries and a non-UTC zone
      (`tests/test_time_properties.py`); store/compare UTC; render local with an explicit offset
      (`render_record`, plus the stated rule in `docs/reference/time.md`). Fixed naive/`Z` `--since`
      handling (a naive ISO no longer breaks an aware comparison; `Z` works on 3.10).

### Task 13 — Q13 (#230): A release pipeline that signs what it ships
- [x] `release.yml`: build → CycloneDX SBOM → keyless Sigstore/cosign signing → SLSA L3 provenance
      (reusable generator) → publish. All GitHub Actions pinned by commit SHA; the build toolchain
      hash-pinned (`scripts/release/requirements-build.txt`). `agentwatch verify-release` accepts a good
      release and rejects a tampered one; the workflow refuses to publish an unverifiable artifact.
