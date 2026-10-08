# Design — Policy from History (advisory)

**BLUF:** How agentwatch derives a **least-privilege permission suggestion** and a **what-if simulation** from observed
behavior, and why it stays advisory: `suggest-policy` emits an inert file/diff; `what-if` replays a policy over history;
nothing is ever applied. Enforcement remains agentpolicy's job.

**Status:** implemented — `suggest-policy` (M30 POL-1, 2026-10-07); `what-if` (M30 POL-2). Sources:
[PRD 55](../prd/55-agent-interfaces-and-policy-from-history.md), [authorization-provenance-v2.md](authorization-provenance-v2.md),
[impact-classification.md](impact-classification.md) (cls1), PRD 45 (ACS). Decision: ADR-0038.

## Why advisory

Prompts are rubber-stamped (~93–97% approved), bypass is common, and broad allow-rules grant arbitrary execution. History
is the only defensible source for a tighter policy — but agentwatch is monitor-only, so the output must be an artifact a
human or agentpolicy applies.

## `suggest-policy`

Inputs: stored calls + cls1 classes + authorization sources (APV) over a window. Output targets:
`claude-settings` | `mcp-allowlist` | `acs`. Produces allow/ask/deny candidates; each rule carries evidence (calls,
sessions, approvals, last-seen). A lint flags dangerous-broad rules (wildcard interpreter/exec, wildcard network).
`command:destructive`, `network:destination`, `credential:adjacent` are **never** suggested as `allow` without an
explicit `--include` and are always annotated. Output states window, record count, coverage gaps and taxonomy version.
Deterministic; read-only; **no write outside `--out`** (test).

> **Implemented (M30 POL-1).** `agentwatch.policy_suggest` groups observed calls by command-scoped matcher
> (`Bash(curl:*)`) or tool, downgrades destructive/network/credential-adjacent classes to `ask` unless
> `--include`, links each rule to evidence, lints broad interpreter/network rules, and emits a target-shaped
> inert document (`claude-settings` / `mcp-allowlist` / `acs`). `--out` is the only file written. Proving test:
> `packages/python-sdk/tests/test_policy_suggest.py`. ADR-0038.

## `what-if`

Replays a candidate policy over history: allowed/asked/denied counts and the delta vs actual behavior (prompts avoided;
would-be denials with sessions; calls whose actual authorization differs). Parse errors explicit; unsupported syntax
reported; output stamped with the policy-format version and labeled a simulation.

## Guardrail

This is the shape that stays inside PRD 14: *"we generate suggestions; we do not apply them."* agentpolicy is the named
consumer; ACS is the interop target (PRD 45). ADR-0038.

## Testing

- No write outside `--out` (FT-POL-1); deterministic (same store → same output).
- Dangerous-broad lint fires; destructive never allow-by-default.
- `what-if` shows measured prompt reduction and lists would-be denials on the field corpus.
