# WBS v0.1.0 — Part 3: Store, Redaction, Export & Replay (M4–M5)

**BLUF:** Harden the **ported** privacy/redaction into a local hash-chained store, then adapt the ported OTLP
export and replay. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M4 — Local store + redaction

**Goal:** adapt the **ported** privacy modes/redaction, then add the local hash-chained store and secret/PII
classes; records are local, redacted, tamper-evident, bounded (R6, R7, R11 early).

**Requirements / PRDs:** R6, R7; [PRD 15](../../prd/15-data-model.md),
[storage design](../../design/storage-design.md), [redaction rules](../../design/redaction-rules.md),
[privacy-mode transforms](../../design/privacy-mode-transforms.md), PRD 17 (F3/F4).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 4.1 | **Port/adapt** privacy modes / redaction | redaction module | 4 modes behave as shipped | #31 |
| 4.2 | Add secret/PII classes + `<REDACTED:kind>` + `secret-detected` event (R5) | rules engine | attack-pack fixtures pass | #32 |
| 4.3 | Add **JSONL store** (append-only, DD-08) | store module | persist + reload | #33 |
| 4.4 | Add **hash chain** + `verify-store` (DD-07) | chain module | any edit detected | #34 |
| 4.5 | Add retention (`retention_days`, `max_size_mb`) | retention | purge tombstones, never silent | #35 |
| 4.6 | Redaction self-test (blocks export, DD-09) | self-test | 0 leaks or export blocked | #36 |
| 4.7 | Fault behavior — store-full (F3) fail-closed; chain-break (F4) surfaced | fault paths | F3/F4 green | #37 |
| 4.8 | **Update design docs** | storage, redaction, privacy, PRD 15 | docs match behavior | #38 |
| 4.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #121 |
| 4.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #122 |

**Tests required:** chain integrity + `verify-store`; F3; F4; redaction attack pack (0 leaks); per-mode
transforms; retention tombstoning.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `verify-store` clean after a session; any edit detected
- [ ] Redaction attack pack finds **0 leaks** (R7); `secret-detected` emitted
- [ ] Store-full fails closed (F3); corrupt chain surfaced (F4); no network (R6)

**Design docs to update:** [storage-design.md](../../design/storage-design.md),
[redaction-rules.md](../../design/redaction-rules.md), [privacy-mode-transforms.md](../../design/privacy-mode-transforms.md),
[privacy-data-handling.md](../../design/privacy-data-handling.md), [PRD 15](../../prd/15-data-model.md),
[PRD 17](../../prd/17-error-handling.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M5 — OTel export + replay

**Goal:** adapt the **ported** OTLP export and replay/timeline tooling so records load into standard OTel
backends unmodified (R4) and any session replays faithfully (R8).

**Requirements / PRDs:** R4, R8; [OTel mapping](../../design/otel-mapping.md),
[record-format spec](../../reference/record-format-spec.md), PRD 17 (F5/F6), DD-09.

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 5.1 | **Port/adapt** OTLP export orchestrator | exporter | records forwarded as OTLP | #39 |
| 5.2 | **Port/adapt** replay / run-timeline concepts | replay module | ordered timeline reconstructable | #40 |
| 5.3 | Adapt exporter to the agentwatch record + security events | mapping | `execute_tool` spans + events | #41 |
| 5.4 | Export gating on redaction self-test (DD-09) | gate | F6 test green | #42 |
| 5.5 | Export resilience — endpoint down keeps local records (F5) | retry/backoff | F5 test green | #43 |
| 5.6 | `agentwatch sessions` + `agentwatch replay <id>` | CLI paths | list + reconstruct | #44 |
| 5.7 | Replay-fidelity automated test | test | diff vs raw transcript empty (R8) | #45 |
| 5.8 | **Update design docs** | otel-mapping, runbook, spec | docs match wiring | #46 |
| 5.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #123 |
| 5.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #124 |

**Tests required:** export to ≥2 backends (Phoenix + Jaeger/Tempo); export-locked-until-self-test; F5/F6;
replay fidelity diff.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Records load unmodified in **≥2** OTel backends (R4)
- [ ] Export blocked until redaction self-test passes (DD-09); export failure loses no data (F5)
- [ ] Replay matches the raw transcript (R8, automated)

**Design docs to update:** [otel-mapping.md](../../design/otel-mapping.md),
[runbooks/export-to-otel.md](../../runbooks/export-to-otel.md), [record-format-spec.md](../../reference/record-format-spec.md),
[CHANGELOG](../../../CHANGELOG.md).

---

Part 3 green ⇒ proceed to [Part 4 (M6–M7)](wbs-v0.1.0-part4-analytics-ui.md).
