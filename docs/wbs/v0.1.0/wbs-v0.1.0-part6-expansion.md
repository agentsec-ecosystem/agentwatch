# WBS v0.1.0 — Part 6: Expansion & Fleet (M10–M11)

**BLUF:** Add the new capabilities in PRD R10 (harness/framework expansion) and R13 (fleet aggregation), plus
drift signals — built on the ported SDK/analytics. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M10 — Harness + framework expansion (R10)

**Goal:** extend beyond Claude Code + LangGraph/raw-Python: Cursor, Codex CLI, Gemini CLI, generic MCP
clients, and Tier-2 framework adapters — via the **ported** adapter/SDK boundary.

**Requirements / PRDs:** R10 ([PRD 05](../../prd/05-features.md)),
[compatibility matrix](../../reference/compatibility.md), [adapter conformance](../../reference/adapter-conformance.md),
[harness-adapter design](../../design/harness-adapter-design.md).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 10.1 | **Port/adapt** adapter API for community harnesses | adapter API | documented + tested |
| 10.2 | Cursor adapter (native hooks; proxy where insufficient) | adapter | conformance green |
| 10.3 | Codex CLI adapter | adapter | conformance green |
| 10.4 | Gemini CLI adapter | adapter | conformance green |
| 10.5 | Generic MCP-client support (proxy tap) | adapter | MCP tool calls recorded |
| 10.6 | Tier-2 adapters (CrewAI, PydanticAI) | adapters | SDK conformance green |
| 10.7 | Per-harness conformance packs (agentdrill-ready) | packs | pass in CI |
| 10.8 | **Update design docs** | compatibility, adapter-conformance, known-limitations | docs match coverage |

**Tests required:** per-harness conformance fixtures; gap assertions; cross-harness trace correlation.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] ≥5 Tier-1 harnesses + ≥3 Tier-2 framework adapters supported (R10)
- [ ] Each adapter's conformance pack passes; gaps documented honestly

**Design docs to update:** [compatibility.md](../../reference/compatibility.md),
[adapter-conformance.md](../../reference/adapter-conformance.md), [harness-adapter-design.md](../../design/harness-adapter-design.md),
[known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M11 — Fleet aggregation (R13) + drift signals

**Goal:** add opt-in, self-hosted **fleet aggregation** (R13) and **drift signal** detection (trailing
baseline) with deployment correlation — extending the ported analytics.

**Requirements / PRDs:** R13, R9 ([PRD 05](../../prd/05-features.md)),
[observability](../../design/observability.md), [analytics design](../../design/data-dictionary.md),
[PRD 13](../../prd/13-non-functional-requirements.md) scale (NFR-7).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 11.1 | **Port/adapt** multi-host ingestion from the analytics layer | ingestion | multiple hosts ingest |
| 11.2 | Fleet aggregation mode (opt-in, self-hosted) | fleet mode | aggregates hosts |
| 11.3 | Drift signal detection (trailing baseline, not fixed thresholds) | drift module | signals emitted as events |
| 11.4 | Deployment correlation overlay | correlation | deploys aligned to metric shifts |
| 11.5 | Fleet + drift tests | tests | aggregation + drift fixtures green |
| 11.6 | **Update design docs** | observability, data-dictionary, PRD 13 | docs match behavior |

**Tests required:** multi-host aggregation; drift detection (baseline vs shift); deployment correlation.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Fleet aggregation aggregates multiple hosts (R13, opt-in)
- [ ] Drift signals emitted from trailing baselines; deployment correlation available

**Design docs to update:** [observability.md](../../design/observability.md), [data-dictionary.md](../../design/data-dictionary.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 6 green ⇒ proceed to [Part 7 (M12–M13)](wbs-v0.1.0-part7-hardening-release.md).
