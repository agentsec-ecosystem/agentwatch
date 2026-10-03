# WBS v0.1.0 — Part 3: Store, Redaction, Export & Replay (M4–M5)

**BLUF:** Harden the **ported** privacy/redaction into a local hash-chained store, then adapt the ported OTLP
export and replay. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M4 — Local store + redaction

**Status:** ✅ **implemented** — execution plan:
[m4-store-redaction-execution-plan.md](../../plans/m4-store-redaction-execution-plan.md); issues #31–#38, #121,
#122. Shipped: `agentwatch.secrets` (secret/PII detection + `<REDACTED:kind>`), the `full` privacy mode,
`agentwatch.store.RecordStore` (append-only hash-chained JSONL), `agentwatch verify-store`, retention
tombstones + size-cap fail-closed (F3), chain-break surfacing (F4), and `agentwatch.selftest` export gate
(DD-09). The daemon persists through the store; `sessions` reads it.

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

- [x] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [x] `verify-store` clean after a session; any edit detected
- [x] Redaction attack pack finds **0 leaks** (R7); `secret-detected` emitted
- [x] Store-full fails closed (F3); corrupt chain surfaced (F4); no network (R6)

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

**Additions (PRD 19–30) landing in M5**

These share the M5 adapter/daemon/CLI surface; full specs in the referenced PRDs.

| # | Addition | Deliverable | Acceptance | PRD | Issue |
|---|---|---|---|---|---|
| 5.A1 | Session boundaries (`SessionStart`/`SessionEnd`) | boundary records | replay brackets sessions; `session-boundaries` gap retired | [19](../../prd/19-agent-lifecycle.md) | #165 |
| 5.A2 | Denied calls (`PermissionDenied`) | `denied` event + record | blocked call recorded; pending Pre retired | [19](../../prd/19-agent-lifecycle.md) | #166 |
| 5.A3 | Prompts as reason steps (`UserPromptSubmit`) | `user-prompt` records | mode-gated; secret-safe | [19](../../prd/19-agent-lifecycle.md) | #167 |
| 5.A4 | Subagent attribution (`agent_id`/`agent_type`) | identity populated | records attributed to subagents | [19](../../prd/19-agent-lifecycle.md) | #168 |
| 5.A5 | Token/model capture from transcript | `session-usage` records | canary test; totals match | [20](../../prd/20-usage-accounting.md) | #169 |
| 5.B1 | `/healthz` self-observability (NFR-12) | health surface | PRD 13 fields; `recording` only when chain intact | [22](../../prd/22-self-observability.md) | #170 |
| 5.B2 | Ecosystem event ingestion | `event emit` | validated, chained, appears in `sessions` | [23](../../prd/23-event-interchange.md) | #171 |
| 5.B3 | Recording gaps as events (F1) | gap records | crash/restart gap chained | [21](../../prd/21-data-integrity.md) | #172 |
| 5.B4 | Quarantine undecodable events (F8) | `quarantine.jsonl` | raw frame preserved; verify green | [21](../../prd/21-data-integrity.md) | #173 |
| 5.C1 | `agentwatch doctor` | doctor command | per-check pass/fail + hint; `--json` | [22](../../prd/22-self-observability.md) | #175 |
| 5.C2 | `agentwatch tail` | tail command | live read-only stream; `-f` | [22](../../prd/22-self-observability.md) | #176 |
| 5.E3 | Four deferred M4 minors | atomic retention, parse errors, Mapping, card regex | four hygiene tests | [21](../../prd/21-data-integrity.md) | #181 |
| 5.F1 | Hook-side spooling | spool + drain | events survive daemon outage | [21](../../prd/21-data-integrity.md) | #182 |
| 5.F2 | Exactly-once ingestion | idempotency key | duplicates no-op; survives restart | [21](../../prd/21-data-integrity.md) | #183 |
| 5.F3 | Export resume cursor (F5) | watermark | no double-export/skip on restart | [21](../../prd/21-data-integrity.md) | #184 |
| 5.F4 | Store format version marker | genesis marker | unknown format rejected | [21](../../prd/21-data-integrity.md) | #185 |
| 5.G1 | `agentwatch verify-privacy` | command | verdict on own config + store | [24](../../prd/24-operator-trust.md) | #188 |
| 5.G3 | Consent-first `init` (+ `--dry-run`) | plan/diff | dry-run writes nothing; uninstall restores exactly | [24](../../prd/24-operator-trust.md) | #190 |
| 5.G4 | `init` preflight | version + trust check | warns with fix hint | [24](../../prd/24-operator-trust.md) | #191 |
| 5.H6 | CLI polish | completions, examples, `--json`, exit codes | completion generates; examples tested | [26](../../prd/26-investigation.md) | #197 |
| 5.O1 | Shared adapter conformance runner | reusable runner | a broken adapter fails CI | [27](../../prd/27-harness-expansion.md) | #216 |
| 5.P1 | Async hooks + published latency | async default + benchmark | under ceiling; ordering test | [28](../../prd/28-performance-operability.md) | #217 |

---

Part 3 green ⇒ proceed to [Part 4 (M6–M7)](wbs-v0.1.0-part4-analytics-ui.md).
