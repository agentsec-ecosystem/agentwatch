# ADR-0038 — Policy suggestion boundary: advisory artifacts only

- **Status:** accepted (2026-10-07, v0.2.0 M30) — implemented
- **Context:** see [PRD 55](../prd/55-agent-interfaces-and-policy-from-history.md) §POL-1/POL-2 and
  [design/policy-from-history.md](../design/policy-from-history.md). Users approve ~93–97% of prompts and
  broad allow-rules grant arbitrary execution; history is the only defensible source for a tighter policy.
  But agentwatch is monitor-only (PRD 14): *"we generate suggestions; we do not apply them."*
- **Decision:** `suggest-policy` and `what-if` are **advisory**. They read the record and emit an **inert**
  artifact (a file via `--out`, a diff, or stdout); they never edit harness settings, never install a policy,
  never block a call, and never write anywhere except `--out`. Rules are evidence-linked, classes
  `command:destructive` / `network:destination` / `credential:adjacent` are never suggested as `allow`
  without an explicit `--include` (and stay annotated), broad rules are linted, and output is deterministic
  with the window, record count, coverage gaps and taxonomy version stated. **agentpolicy** is the named
  consumer and **ACS** is the interop target (PRD 45); `what-if` output is labeled a simulation and stamped
  with the policy-format version.
- **Consequences:** A whole class of "the recorder silently changed my permissions" incidents is closed by
  construction. The suggestion's quality is bounded by captured arguments: metadata-only records that cannot
  be scoped surface as explicit coverage gaps rather than guessed rules (see
  [known-limitations.md](../reference/known-limitations.md)).
