# PRD 55 — Agent Interfaces & Policy-from-History

**BLUF:** Make the record usable *by* agents and turn history into a defensible policy artifact. A read-only MCP server,
a shipped investigation skill, and a versioned CLI JSON contract let coding/IR agents query the record safely; and
`suggest-policy` / `what-if` derive least-privilege permission candidates from observed behavior — **advisory only**,
never applied by agentwatch.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M27–M28 ·
**Depends on:** PRD 49 (APV), PRD 31 (S21), PRD 36 (S8), PRD 45 (ACS) · **Extends:** H3 search, H6 JSON, `inventory`,
cls1, "no policy-overlay view" limitation · **Adds:** CUJ-26, CUJ-27

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic; monitor-only, R2; local-first/no-egress (R6); no new runtime dependency without a decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **agentwatch generates and simulates; it never enforces.** Enforcement is agentpolicy; scanning is
agentdrill. Giving an agent read access is itself a trust surface (OWASP ASI01/ASI06) and is bounded accordingly.

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| AGI-1 | Read-only MCP server over the record | Observability vendors ship MCP+CLI "for agents"; IR is agent-assisted | 26 |
| AGI-2 | Investigation skill + versioned CLI JSON schemas | Adoption is driven by a drop-in skill and a stable contract | 26 |
| POL-1 | `suggest-policy` least-privilege candidates + broad-rule lint | Prompts are rubber-stamped; least privilege needs evidence | 27 |
| POL-2 | `what-if` policy replay over history | Operators won't adopt a policy blind | 27 |

## AGI-1 — Read-only MCP server · (new)

**Why.** Langfuse ships a CLI, a platform MCP server (15 tool categories) and a `SKILL.md`; agentwatch is the record of
what those agents did but exposes no agent-usable interface (its only "MCP" is the interposition proxy). Reviewers',
IR agents and the coding agent itself are natural consumers.

**Behavior.** `agentwatch mcp-serve` exposes a small read-only tool set — sessions, search, replay, impact, blame,
coverage, cost, oversight, provenance, inventory diff — returning structured results with record IDs.

**Acceptance.**
- [ ] Read-only by construction: no tool mutates store/config/hooks (a test enumerates tools and asserts).
- [ ] Responses labeled **untrusted data with record citations**; already redacted; metadata-only default means no raw
      content to inject (ADR-0024 posture extended; fuzz-tested against injection-shaped record content) (FT-AGI-1).
- [ ] Every query recorded as `store-access` (S21).
- [ ] Opt-in per project; off by default; consent-first install; byte-identical removal; bounded results + rate limit.

**Security & privacy.** Local stdio; record already redacted; no free-form query beyond the filter grammar.
**Dependencies.** APV (authorization in results), S21, PRD 50 (install).
**Risks & mitigations.** Injection via record content; agent reading its own history → untrusted labeling + fuzz + option
to ship AGI-2 alone if the review rejects the server. **Decision.** ADR-0037.

## AGI-2 — Investigation skill + CLI JSON contract · (new)

**Why.** Same sources; agent adoption is driven by a skill and a stable machine contract.
**Behavior.** A shipped skill teaching coding agents the investigation workflow, and versioned JSON schemas for every
read command's `--json` (HTTP contract is PRD 46 API-1).
**Acceptance.** Skill tested by a scripted agent against the demo store reaching documented answers; CLI JSON schemas
published in `schema/` with changelog-enforced stewardship.
**Dependencies.** AGI-1 (optional), API-1.

## POL-1 — `suggest-policy` · (new)

**Why.** Users approve 93–97% of prompts; sandboxes cut prompts 84%; Anthropic warns overly broad allow-rules grant
arbitrary code execution; the community already runs record→infer→lock→enforce; Microsoft/OWASP prescribe least-privilege
scoping. Only a tamper-evident history yields a *defensible* suggestion, and agentwatch must stay monitor-only.

**Behavior.** `agentwatch suggest-policy --since 30d [--project] --target <claude-settings|mcp-allowlist|acs>` emits a
proposed allow/ask/deny set from observed calls + cls1 classes, a lint of dangerous-broad rules, and "observed but never
recommend allowing" (destructive/network/credential-adjacent). Advisory only; output is a file/diff.

**Acceptance.**
- [ ] Never edits harness settings (test asserts no write outside `--out`).
- [ ] Each rule shows evidence (n calls, sessions, approvals, last seen).
- [ ] Broad-rule lint flags wildcard interpreter/exec and wildcard network rules (FT-POL-1).
- [ ] Destructive/network/credential-adjacent never suggested as `allow` without explicit `--include`; always annotated.
- [ ] Output states window, record count, coverage gaps; deterministic.

**Security & privacy.** Read-only; deterministic; no LLM.
**Dependencies.** APV-1, cls1, ACS (PRD 45) for the ACS target.
**Risks & mitigations.** Read as enforcement → inert file + wording + agentpolicy named as consumer. **Decision.** ADR-0038.

## POL-2 — `what-if` · (new)

**Why.** Operators want "what would this policy have blocked / prompted last month?" before enforcing; it is the
confidence step and the bridge to agentpolicy.
**Behavior.** `agentwatch what-if <policy-file> --since 30d` reports allowed/asked/denied counts and the delta vs actual.
**Acceptance.** Table of prompts avoided, would-be-denied calls (with sessions), and calls whose actual authorization
differs; parse errors explicit; unsupported syntax reported; output stamped with policy-format version; labeled simulation.
**Dependencies.** POL-1. **Decision.** ADR-0038.

## Not goals
Enforcement, live blocking, policy-authoring UX, agentdrill scanning, letting agents mutate the record via MCP.

## Sources
langfuse.com changelog/Launch Week 5; LangSmith platform; Anthropic auto-mode/containment posts; agentperms; Microsoft
least-privilege blog; OWASP AI Agent Security Cheat Sheet; AuthBench. Local analysis files 04, 07.
