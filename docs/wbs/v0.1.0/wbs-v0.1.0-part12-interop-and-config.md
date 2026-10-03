# WBS v0.1.0 — Part 12: Interop & Configuration (M20–M21)

**BLUF:** Emit open standards and make the recorder legible and safe to live with. PRDs 31–39, all in v0.1.0. Field Tests (M23) and Release Readiness (M24) remain the last two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M20 — Standards & Interop (PRD 36)

**Status:** ☐ not started

**Goal:** Emit and consume open standards: OCSF/CloudEvents, a reference consumer, an OTel collector component, opt-in event forwarding sinks, and MCP tool-surface drift as a new security event.

**Requirements / PRDs:** [PRD 36](../../prd/36-standards-and-interop.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 20.S8 | OCSF + CloudEvents mappings for the security-event schema | feature + tests | Every shipped event type maps to a documented OCSF target or an explicit `unmapped` | #260 |
| 20.S38 | A reference consumer, not just a contract | feature + tests | The example runs in CI against a fixture event stream and validates each event | #261 |
| 20.S39 | An OTel Collector component | feature + tests | The component's output validates against the pinned semconv | #262 |
| 20.S10 | Security-event forwarding sink (file / webhook / syslog), opt-in, rule-free | feature + tests | A configured file sink receives events | #263 |
| 20.S4 | MCP tool-surface snapshot + drift | feature + tests | A server whose tool set changes between two sessions emits one `tool-surface-changed` with | #264 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] OCSF/CloudEvents/CycloneDX outputs validate against pinned schemas; `tool-surface-changed` follows W5 stewardship.

**Design docs to update:** [PRD 36](../../prd/36-standards-and-interop.md), [PRD 23](../../prd/23-event-interchange.md), [PRD 27](../../prd/27-harness-expansion.md)

---

## Milestone M21 — Configuration, Profiles & Capture Hygiene (PRD 37)

**Status:** ☐ not started

**Goal:** Make the recorder legible and safe: config explain, install profiles, a pathological-record guard, the SDK/hook read-time union, and a standalone redactor.

**Requirements / PRDs:** [PRD 37](../../prd/37-config-and-capture-hygiene.md) · full detail in the PRD sections.

**Work items**

| # | Task | Deliverable | Acceptance | Issue |
|---|---|---|---|---|
| 21.S34 | `agentwatch config explain` | feature + tests | A key set at three layers reports the winning layer and the overridden ones | #265 |
| 21.S35 | Install profiles | feature + tests | Each profile validates | #266 |
| 21.S36 | Guard the single pathological record | feature + tests | An oversized response is truncated with a marker naming the field and original size | #267 |
| 21.S11 | Close the P5 hole — read-time union of SDK spans and harness records | feature + tests | A query returns both sources with `source` set | #268 |
| 21.S13 | The redactor as a reusable, standalone primitive | feature + tests | The filter masks the corpus the same way the write path does | #269 |

**Tests required:** per-item tests as listed; all new paths covered; coverage ≥ 95%.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated
- [ ] `config explain` never prints secret values; profiles validate; oversized records truncate visibly.

**Design docs to update:** [PRD 37](../../prd/37-config-and-capture-hygiene.md), [PRD 16](../../prd/16-configuration.md), [cli-reference](../../reference/cli-reference.md)

---
