# WBS v0.1.0 — Part 6: Expansion & Fleet (M10–M11)

**BLUF:** Add the new capabilities in PRD R10 (harness/framework expansion) and R13 (fleet aggregation), plus
drift signals — built on the ported SDK/analytics. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M10 — Harness + framework expansion (R10)

**Status:** ✅ **complete** — Phase 1 (published adapter/store/daemon contract), Phase 2 (provisional
modeled Cursor / Codex CLI / Gemini CLI adapters), Phase 3 (MCP interposition proxy: adapter, stdio relay,
daemon `phase: "mcp"`, **HTTP/SSE**, `init --mcp-proxy` install + byte-exact `uninstall` restore), Phase 4
(provisional modeled **Tier-2** CrewAI / PydanticAI adapters), and Phase 5 (**OTel/NDJSON ingestion**,
deterministic **fake-harness emitters**, and a **generated compatibility table + nightly version-drift
matrix**) all landed.

**Goal:** extend beyond Claude Code + LangGraph/raw-Python: Cursor, Codex CLI, Gemini CLI, generic MCP
clients, and Tier-2 framework adapters — via the **ported** adapter/SDK boundary.

**Requirements / PRDs:** R10 ([PRD 05](../../prd/05-features.md)),
[compatibility matrix](../../reference/compatibility.md), [adapter conformance](../../reference/adapter-conformance.md),
[harness-adapter design](../../design/harness-adapter-design.md), [MCP proxy design](../../design/mcp-proxy-design.md)
([Plan A](../../plans/mcp-proxy-stdio-execution-plan.md)).

**Progress:** ✅ 10.1–10.8 and 10.T/10.D (adapter API + modeled Cursor / Codex CLI / Gemini CLI / CrewAI /
PydanticAI + generic MCP proxy tap + docs/tests), 10.7 (conformance packs), 10.J1 (plumbing contract),
10.N1 (MCP proxy — Plan A stdio + Plan B HTTP/SSE + `init --mcp-proxy` install/restore), 10.N2 (OTel/NDJSON
ingestion), 10.N3 (fake-harness emitters), 10.N4 (generated compatibility table + nightly drift matrix).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 10.1 | ✅ **Port/adapt** adapter API for community harnesses | adapter API | documented + tested | #79 |
| 10.2 | ✅ Cursor adapter (provisional, modeled) | adapter | conformance green | #80 |
| 10.3 | ✅ Codex CLI adapter (provisional, modeled) | adapter | conformance green | #81 |
| 10.4 | ✅ Gemini CLI adapter (provisional, modeled) | adapter | conformance green | #82 |
| 10.5 | ✅ Generic MCP-client support (proxy tap) — stdio recording + conformance; HTTP/SSE tracked in 10.N1 | adapter | MCP tool calls recorded | #83 |
| 10.6 | ✅ Tier-2 adapters (CrewAI, PydanticAI, provisional modeled) | adapters | SDK conformance green | #84 |
| 10.7 | ✅ Per-harness conformance packs (agentdrill-ready) | packs | pass in CI | #85 |
| 10.8 | ✅ **Update design docs** | compatibility, adapter-conformance, known-limitations | docs match coverage | #86 |
| 10.T | ✅ Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #133 |
| 10.D | ✅ Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #134 |

**Tests required:** per-harness conformance fixtures; gap assertions; cross-harness trace correlation.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] ≥5 Tier-1 harnesses + ≥3 Tier-2 framework adapters supported (R10)
- [ ] Each adapter's conformance pack passes; gaps documented honestly

**Design docs to update:** [compatibility.md](../../reference/compatibility.md),
[adapter-conformance.md](../../reference/adapter-conformance.md), [harness-adapter-design.md](../../design/harness-adapter-design.md),
[known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

**Additions (PRD 19–30) landing in M10**

| # | Addition | Deliverable | Acceptance | PRD | Issue |
|---|---|---|---|---|---|
| 10.J1 | ✅ Publish the plumbing contract | store + socket specs | sample external adapter passes conformance | [23](../../prd/23-event-interchange.md) | #203 |
| 10.N1 | ✅ MCP-client interposition adapter (stdio + HTTP/SSE; `init --mcp-proxy` install/restore) | `init --mcp-proxy` | records both directions; restores config exactly | [27](../../prd/27-harness-expansion.md) | #212 |
| 10.N2 | ✅ OTel GenAI ingestion | `ingest --format otel` | fixture trace chains + validates | [27](../../prd/27-harness-expansion.md) | #213 |
| 10.N3 | ✅ Fake-harness emitters | per-platform generators | long-running paths covered deterministically | [27](../../prd/27-harness-expansion.md) | #214 |
| 10.N4 | ✅ Generated compatibility table + version matrix | version-tagged fixtures + drift job | drift opens an issue; table generated | [27](../../prd/27-harness-expansion.md) | #215 |

---

## Milestone M11 — Fleet aggregation (R13) + drift signals

**Status:** ✅ **complete** — implemented local-first in the SDK (per the human partner's decision, rather
than the Postgres analytics service): a `host` record tag, `agentwatch.fleet` (multi-host ingestion +
rollups), and `agentwatch.drift` (trailing-baseline signals emitted as a new `drift-detected` security
event, plus deployment correlation). CLIs: `agentwatch fleet`, `agentwatch drift`.

**Goal:** add opt-in, self-hosted **fleet aggregation** (R13) and **drift signal** detection (trailing
baseline) with deployment correlation.

**Requirements / PRDs:** R13, R9 ([PRD 05](../../prd/05-features.md)),
[observability](../../design/observability.md), [analytics design](../../design/data-dictionary.md),
[PRD 13](../../prd/13-non-functional-requirements.md) scale (NFR-7).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 11.1 | ✅ **Adapt** multi-host ingestion (SDK `agentwatch.fleet`) | ingestion | multiple hosts ingest | #87 |
| 11.2 | ✅ Fleet aggregation mode (opt-in, self-hosted) | fleet mode | aggregates hosts | #88 |
| 11.3 | ✅ Drift signal detection (trailing baseline, not fixed thresholds) | drift module | signals emitted as `drift-detected` events | #89 |
| 11.4 | ✅ Deployment correlation overlay | correlation | deploys aligned to metric shifts | #90 |
| 11.5 | ✅ Fleet + drift tests | tests | aggregation + drift fixtures green | #91 |
| 11.6 | ✅ **Update design docs** | observability, record-format, cli-reference, PRD 13 | docs match behavior | #92 |
| 11.T | ✅ Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #135 |
| 11.D | ✅ Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #136 |

**Tests required:** multi-host aggregation; drift detection (baseline vs shift); deployment correlation.

**Exit criteria**

- [x] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [x] Fleet aggregation aggregates multiple hosts (R13, opt-in)
- [x] Drift signals emitted from trailing baselines; deployment correlation available

**Design docs to update:** [observability.md](../../design/observability.md), [data-dictionary.md](../../design/data-dictionary.md),
[PRD 13](../../prd/13-non-functional-requirements.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 6 green ⇒ proceed to [Part 7 (M12–M13)](wbs-v0.1.0-part7-hardening-release.md).
