# WBS v0.1.0 — Part 10: Recorder Trust & Investigation (M16–M17)

**BLUF:** Answer "did you capture everything?" and convert sessions into investigation answers. PRDs 31–39, all in v0.1.0. Field Tests (M23) and Release Readiness (M24) remain the last two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M16 — Coverage & Recorder Trust (PRD 32)

**Status:** ☐ not started

**Goal:** Answer "did you capture everything?": coverage reconciliation, recorder-state audit records, the harness-drift canary, quarantine tooling, the recorder attack suite, and segment archiving.

**Requirements / PRDs:** [PRD 32](../../prd/32-coverage-and-recorder-trust.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 16.S2 | `agentwatch coverage` — reconcile the store against ground truth | feature + tests | A seeded gap of each class is classified with the right cause | #238 |
| 16.S5 | Recorder-state audit records — close the "quietly turned off" hole | feature + tests | `init`/`uninstall`/privacy downgrade each append one marker | #239 |
| 16.S19 | Harness-drift canary from real traffic | feature + tests | A fixture with an unknown top-level field emits one debounced observation naming the field and | #240 |
| 16.S27 | Operator tooling for the quarantine | feature + tests | Requeue after a fix moves an entry into the store | #241 |
| 16.S30 | Treat the recorder as an attack target | feature + tests | Each anti-forensics scenario has a test asserting the documented detection (or the documented | #242 |
| 16.S28 | Seal and archive old segments | feature + tests | Archive then verify the segment independently | #243 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] `coverage` classifies every gap and `gap:unexplained` is zero on fixtures; recorder-attack matrix published.

**Design docs to update:** [PRD 32](../../prd/32-coverage-and-recorder-trust.md), [PRD 22](../../prd/22-self-observability.md), [PRD 06](../../prd/06-security-baseline.md)

---

## Milestone M17 — Investigation & Impact (PRD 33)

**Status:** ☐ not started

**Goal:** Convert sessions into investigation answers: change footprint, subagent tree, file blame, cross-session time window, denied-then-retried sequences, behavior fingerprint, interrupt capture, digest, and local cost.

**Requirements / PRDs:** [PRD 33](../../prd/33-investigation-and-impact.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 17.S3 | `agentwatch impact` — the change footprint (blast radius) of a session | feature + tests | Two fixture sessions produce hand-derived footprints | #244 |
| 17.S17 | `agentwatch tree <session>` — the subagent fan-out | feature + tests | A fixture with two parallel subagents renders two siblings with correct counts | #245 |
| 17.S18 | `agentwatch blame <path>` — the file-centric reverse index | feature + tests | Two sessions touching one path list newest-first | #246 |
| 17.S24 | `agentwatch at <time>` — the cross-session time window | feature + tests | Two sessions in one window render time-ordered | #247 |
| 17.S25 | Surface denied-then-retried sequences | feature + tests | A fixture denial followed by a different-route retry surfaces the follow-up | #248 |
| 17.S7 | Session behavior fingerprint — a stable hash of what the agent did | feature + tests | Two identical action sequences share a digest | #249 |
| 17.S33 | Capture the human interrupt | feature + tests | An explicit interrupt yields `interrupted-by-user` | #250 |
| 17.S37 | `agentwatch digest` — the local weekly readout | feature + tests | A seeded week produces a digest naming sessions/cost/gaps | #251 |
| 17.S6 | `agentwatch cost` — make the captured usage answerable | feature + tests | A fixture session rolls up to the hand-derived dollar value | #252 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] Every view renders hand-derived results; behavior digest stable and versioned.

**Design docs to update:** [PRD 33](../../prd/33-investigation-and-impact.md), [PRD 26](../../prd/26-investigation.md), [cli-reference](../../reference/cli-reference.md)

---
