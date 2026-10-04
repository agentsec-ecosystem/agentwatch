# PRD 38 — Engineering Rigor

**BLUF:** Raise the engineering floor so the product's claims are *measured*, not asserted: property-based and
differential redaction testing, mutation and fuzz testing on the trust path, a CI that runs the whole repo, an
enforced performance budget, published conformance vectors, a forward-compatibility matrix, a machine-readable
error contract, a claims ledger, executable docs, an accessibility conformance level, time correctness, and a
release pipeline that signs what it ships.

**Status:** proposed (2026-10-03) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only,
> every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency
> without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

These are findings from `Makefile`, `.github/workflows/`, and `pyproject.toml` against what the PRDs promise.
They are **test/CI/tooling** work: they add no product surface except where a claim needs a command (Q9, Q13).

### Q1. Property-based + differential redaction testing · v0.1.0 · (new · highest-value quality item)

**Why.** "Zero secret leaks" is the binary trust claim (PRD 07), and it rests on a **fixed corpus**
(`agentwatch.selftest`, DD-09). A fixed corpus measures *regression*, not *recall*: it cannot find the secret
shape nobody thought of, which is the failure mode that matters.

**What.** (a) Hypothesis strategies generating secret-shaped strings (key prefixes, base64url bodies, JWT
triplets, connection strings) under mutation (whitespace, encoding, chunking, unicode confusables), asserting
no plaintext survives; (b) a **differential oracle** running the same corpus through `gitleaks`/`detect-secrets`
rules and asserting agentwatch's recall is ≥ theirs, reporting any rule-class missed.

**Data & schema impact.** Test-only; new dev dependencies (`hypothesis`, an oracle) recorded per NFR-5.

**Security & privacy.** Test-only; generates synthetic secret-shaped strings, never real secrets.

**Edge cases.** A generated string that is not actually a secret → excluded from recall math; an oracle rule
class agentwatch misses → reported as a finding, not a silent pass.

**Dependencies.** M4 `selftest`, DD-09, W5 (published results).

**Testing.** The property test fails on a seeded unredacted secret shape; the differential test reports a
missing rule-class as a failure.

**Risks & mitigations.** Oracle rules drifting → pin oracle versions; recall measured against a pinned set.

**Decision.** New — oracle choice and the surviving-recall gate.

### Q2. Mutation testing on the trust path · v0.1.0 · (new)

**Why.** 95% coverage says lines ran, not that assertions catch a defect. For three modules — chain/store,
redaction, `validate_record`/`validate_event` — tests passing while the code is wrong is the whole risk. L1
already asks for a mutation check on detectors; apply the same standard where it matters most.

**What.** `mutmut`/`cosmic-ray` scoped to those modules, with a surviving-mutant budget gated in CI. Not
repo-wide.

**Data & schema impact.** Test-only; dev dependency recorded.

**Security & privacy.** Test-only.

**Edge cases.** Equivalent mutants → excluded via a documented allow-list, not by lowering the budget.

**Dependencies.** Trust-path modules (M2/M4).

**Testing.** CI fails when survivors exceed the budget; the allow-list is reviewed.

**Risks & mitigations.** Equivalent-mutant noise → scoped allow-list + budget.

**Decision.** New — tool choice and budget.

### Q3. Fuzzing the parsers, now rather than before v1.0 · v0.1.0 · (new)

**Why.** PRD 18 §D promises "fuzzed parsers (MCP JSON-RPC, record schema) — target OSS-Fuzz before v1.0."
Every untrusted-input surface already exists in v0.1.0: hook JSON, socket frames, store lines, transcripts (H1),
MCP messages (N1).

**What.** Atheris/Hypothesis harnesses for each, run nightly with a committed corpus; OSS-Fuzz submission as
the v1.0 step.

**Data & schema impact.** Test-only; nightly CI job; dev dependency recorded.

**Security & privacy.** Test-only; synthetic inputs.

**Edge cases.** A crash found → minimized input committed as a regression case; a hang → bounded-time harness.

**Dependencies.** M3/M4 parsers, H1, N1.

**Testing.** Each harness runs in CI; a seeded malformed input is contained (rejected/quarantined, never a
crash).

**Risks & mitigations.** Fuzzing wall-time → nightly, bounded per-harness budget.

**Decision.** New — harness coverage and nightly budget.

### Q4. Enforce the performance budget in CI · v0.1.0 · (new)

**Why.** `docs/design/performance-budget.md` specifies "performance test in CI … fail if p99 > 5 ms";
`.github/workflows/ci.yml` runs lint, mypy, and pytest only. NFR-1 (≤5 ms/step) and P1's "published latency
number" are measured once by hand and defended by nobody. A recorder that silently slows down is one people
turn off — and "kept it on >70%" is the top success metric.

**What.** A `pytest-benchmark` job with a committed baseline, a p99 gate, and the published number generated
from the run rather than written in prose.

**Data & schema impact.** CI + a committed baseline; no product change.

**Security & privacy.** None.

**Edge cases.** CI machine variance → a documented tolerance band; a regression → the job fails with the
delta.

**Dependencies.** Performance budget doc, M12 perf hooks.

**Testing.** A deliberate slowdown fails the gate; the published number is generated from the run.

**Risks & mitigations.** Flaky CI timings → tolerance band + baseline refresh policy.

**Decision.** New — tolerance band and baseline source.

### Q5. Make CI run the whole repo · v0.1.0 · (new)

**Why.** `make test` runs the three Python packages and `tests/`; it does **not** run `apps/web` unit tests,
the axe a11y tests landed in M7 (#63), or the Playwright E2E specs (M8). Three milestones of verification exist
and are undefended by CI — a11y and E2E will rot within weeks. This is the single highest-leverage CI change
and it is hours of work.

**What.** CI jobs for web unit + axe, Playwright E2E against the compose stack, the **no-network E2E** (K2, a
*claim test* for local-first, not a nicety), and a docker-stack smoke test. Wire them into the workflow(s)
alongside `ci.yml`.

**Data & schema impact.** CI only; no product change.

**Security & privacy.** None; the no-network E2E asserts local-first.

**Edge cases.** CI without Docker → the compose/E2E jobs skip with a clear reason, never silently pass; the
no-network test is a hard gate where it can run.

**Dependencies.** M7 (a11y), M8 (E2E, seed), K2 (no-network), compose stack.

**Testing.** The new jobs run green on the current tree; a seeded a11y/E2E regression fails them.

**Risks & mitigations.** CI duration/cost → split jobs, cache; required vs informational jobs documented.

**Decision.** New — job split and required-check set.

### Q6. Publish conformance test vectors for the store and chain · v0.1.0 · (new)

**Why.** J1 publishes the format; a format without vectors is not independently implementable (the JOSE/COSE
lesson). Third-party verifiers (S12), community adapters (R10), and ecosystem consumers all need "here is a
store, here are its hashes, here is a tampered one that must fail."

**What.** `schema/vectors/` with valid/tampered/tombstoned/purged/gap/checkpoint cases, plus a published
expected-verdict table that both `store.py` and the standalone verifier (S12) run against.

**Data & schema impact.** New published vectors; no record change.

**Security & privacy.** None.

**Edge cases.** A vector whose verdict differs between implementations → a contract bug, surfaced.

**Dependencies.** J1, S12, M4 store.

**Testing.** `store.py` and the standalone verifier both match the expected-verdict table.

**Risks & mitigations.** Vectors diverging from the spec → generated from the documented envelope rules.

**Decision.** New — vector set and verdict-table format.

### Q7. Forward-compatibility test matrix for stored data · v0.1.0 · (new)

**Why.** F4 added a store format-version marker and F8 rejects unknown versions — good. Nothing tests that
**today's code reads yesterday's store**, the guarantee that matters to anyone who leaves the recorder on for a
year.

**What.** Commit a frozen store per released format version; CI asserts every one still reads, verifies,
replays, and exports. Grow the set per release.

**Data & schema impact.** New frozen-store fixtures; no product change.

**Security & privacy.** Frozen stores contain no secrets (synthesized).

**Edge cases.** A format change that breaks an old store → caught before release; an old store with an inferred
`producer` (S26) → reads as `hook` with a format-version note.

**Dependencies.** F4/F8, S26, W5.

**Testing.** Every frozen store reads/verifies/replays/exports in CI.

**Risks & mitigations.** Frozen fixtures growing stale → grown per release; each removed only at a major.

**Decision.** New — fixture set and retention across versions.

### Q8. One machine-readable error contract · v0.1.0 · (new)

**Why.** H6 promises documented exit codes and `--json` on read commands. For a tool meant to be scripted by
sibling projects and CI, errors need the same contract as success.

**What.** A single error envelope (`{"error": {"code","message","hint","doc_url"}}`), one exit-code table
generated from the code (not hand-maintained), and a test asserting every command's failure path emits it.

**Data & schema impact.** New error schema + generated exit-code table; no record change.

**Security & privacy.** None; must never include a secret value in a message.

**Edge cases.** An unknown failure → a catch-all code with the doc URL; a usage error (argparse) → mapped to
the documented exit code.

**Dependencies.** H6, CLI (`main.py`).

**Testing.** Every subcommand's failure path emits the envelope with a code; the generated table matches the
codes.

**Risks & mitigations.** Hand-maintained drift → generate the table from the code + test.

**Decision.** New — envelope shape and exit-code table generation.

### Q9. A claims ledger · v0.1.0 · (new)

**Why.** PRD 18 says "we don't claim what we can't prove" and PRD 12 traces requirements → CUJ → WBS → test.
Nothing traces the **public claims** — the press release, README, and docs sentences a reviewer will challenge
("zero leaks", "≤15 min", "no network required", "tamper-evident", "loads into two backends").

**What.** `docs/release/claims-ledger.md`: each public claim → exact wording → the test/evidence id → last
verified date. A CI check fails when a claim has no live evidence link.

**Data & schema impact.** New docs + a CI check; no product change.

**Security & privacy.** None.

**Edge cases.** A claim with no evidence → CI fails (add evidence or remove the claim); an evidence test
renamed → link breaks and fails.

**Dependencies.** PRD 12 traceability, PRD 18, CI.

**Testing.** The ledger check fails on a claim without an evidence link and passes on the current set.

**Risks & mitigations.** Ledger drift → CI enforcement + release-gate review.

**Decision.** New — ledger schema and which claims are in scope.

### Q10. Executable documentation · v0.1.0 · (new)

**Why.** J3's cookbook and the tutorials are the onboarding path and will drift as the CLI evolves —
`26-investigation.md:184` names this risk and leaves it to link-checking.

**What.** Extract fenced commands from tutorials/cookbook and run them against the seed dataset in CI. Docs
that cannot execute are a build failure, not a stale page.

**Data & schema impact.** CI + doc conventions; no product change.

**Security & privacy.** Uses the synthetic seed dataset only.

**Edge cases.** A command that needs network → marked and skipped; a command that needs a service → the
compose-backed job from Q5 covers it.

**Dependencies.** J3, M8 seed, Q5.

**Testing.** The extracted-command job passes on the current docs; a broken command fails it.

**Risks & mitigations.** Over-broad extraction → an explicit fenced-block annotation.

**Decision.** New — which docs are executable and how blocks are marked.

### Q11. State an accessibility conformance level · v0.1.0 · (new)

**Why.** NFR-10 says "basic a11y (keyboard, contrast, labels)" — not a standard anyone can accept or reject.
axe tests now exist (#63), so the hard part is done and the claim is simply unstated.

**What.** Target **WCAG 2.2 AA**, publish a short conformance statement per view (VPAT-lite), add a
keyboard-only E2E path through the flagship journey (CUJ-8), and run axe in CI (Q5). Required for public-sector
and most enterprise procurement.

**Data & schema impact.** Docs + E2E; no product surface change beyond fixes any test surfaces.

**Security & privacy.** None.

**Edge cases.** A view failing a criterion → listed with a remediation. Axe under jsdom disables contrast
(existing #63 note); a Playwright contrast check covers it.

**Dependencies.** M7 (#63 axe), Q5, PRD 04 CUJ-8.

**Testing.** A keyboard-only E2E traverses CUJ-8; axe runs in CI; the conformance statement matches results.

**Risks & mitigations.** Claiming AA without contrast coverage in CI → add the Playwright contrast check.

**Decision.** New — WCAG version/level and statement shape.

### Q12. Time correctness as a tested property · v0.1.0 · (new)

**Why.** B5 detects clock skew and durations use the monotonic clock — the hard parts are handled. Everything
else (`--since 2d`, day-bucketed cost, retention windows, DST, cross-timezone bundles) is ordinary code where
off-by-a-day bugs are invisible until an auditor finds one.

**What.** Store and compare UTC everywhere, render local with an explicit offset, and property-test the
`--since` parser and day bucketing across DST boundaries and a non-UTC default timezone.

**Data & schema impact.** Test-only + a stated rendering rule; no record change.

**Security & privacy.** None.

**Edge cases.** DST spring-forward/fall-back, `--since` straddling midnight, a bundle produced in one timezone
and read in another.

**Dependencies.** B5, query/since, S24, retention.

**Testing.** Property tests over DST boundaries and non-UTC defaults pass; a bundle renders with an explicit
offset.

**Risks & mitigations.** Timezone assumptions in rendering → UTC store + explicit-offset render everywhere.

**Decision.** New — the rendering rule and property-test scope.

### Q13. A release pipeline that actually signs what it ships · v0.1.0 · (new)

**Why.** `.github/workflows/` contains `ci.yml`, `dco.yml`, `scorecard.yml` — **no release workflow.** WBS
13.5/15.4 and PRD 18 §F require SBOM, signed artifacts, and SLSA provenance at the release gate, so today they
are a manual checklist on the critical path of a security product's first release. The Plugin4Shell lesson PRD
18 §D applies to agentwatch is, right now, not applied to agentwatch.

**What.** A `release.yml` doing: build → CycloneDX SBOM → Sigstore/cosign signing → SLSA L3 provenance via the
reusable generator → publish, with GitHub Actions pinned by commit SHA and hash-pinned Python deps. Then
`agentwatch verify-release` so a user can check what they installed.

**Data & schema impact.** New workflow + a verify command; no record change.

**Security & privacy.** Supply-chain integrity; the workflow has no secret egress beyond the release itself.

**Edge cases.** An unsigned artifact → release fails; a provenance mismatch → `verify-release` fails with the
reason.

**Dependencies.** PRD 18 §D/§F, WBS 13.5/15.4, M15 release tooling.

**Testing.** A dry-run release produces SBOM + signature + provenance; `verify-release` accepts a good artifact
and rejects a tampered one.

**Risks & mitigations.** Action supply-chain risk → pin actions by SHA + hash-pinned deps.

**Decision.** New — signing tool and provenance level (SLSA L3 target).
