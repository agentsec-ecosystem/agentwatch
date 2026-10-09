# Glossary

**BLUF:** Shared vocabulary for agentwatch and the agentsec-ecosystem. Complements the org glossary.

| Term | Meaning |
|---|---|
| **Record** | A normalized agent activity entry (a tool call / behavior span) in the agentwatch format. |
| **Span** | An OpenTelemetry unit of work; agentwatch uses OTel GenAI `execute_tool` spans. |
| **Security event** | A named, versioned event (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`). |
| **Harness** | The agent runtime being recorded (Claude Code, Cursor, Codex CLI, Gemini CLI, frameworks). |
| **Adapter** | The contract that maps a harness's native events into agentwatch records. |
| **Detector** | A rule-based or LLM-augmented signal that flags an anomaly (35 rule + 5 LLM in the shipped project). |
| **Cohort** | A set of runs grouped by agent name/version/workload, used for comparison. |
| **Redaction** | Removing/altering argument values before storage (privacy modes: metadata-only, truncated, hashed, full). |
| **Hash chain** | A tamper-evident link between successive stored records. |
| **Parity** | The requirement that every capability shipped in `agent-exec-trace` is delivered by agentwatch. |
| **Fail-closed** | On tamper/failure, agentwatch surfaces the problem rather than silently stopping. |
| **Meta-MVP** | The Wave 0 ecosystem release: one brand, one install, all four capabilities. |
| **AAT** | IETF **Agent Audit Trail** — the exported, hash-chained audit bundle (`schema/`, draft-sharif-agent-audit-trail-06); verified by an independent consumer. |
| **MCP** | Model Context Protocol — agentwatch interposes (`mcp-proxy`) and serves read-only (`mcp-serve`); tools/resources/prompts/elicitation/tasks recorded. |
| **A2A** | Agent2Agent protocol — interposed by `a2a-proxy`; agent-card signatures verified (never an authorization); hand-offs recorded as `agent-delegation`. |
| **Sampler** | Deterministic security-relevant sampling (security events/denials/errors are never sampled out). |
| **Workload identity / credential class** | The agent's identity dimension (`workload_identity`, `credential_class` — e.g. `ambient`/`shared`); absent is never invented. |
| **Capability / capability drift** | Inventoried plugins, hooks, skills, rules, MCP servers, memory stores + their content digests; drift is "content changed, version unchanged" (Plugin4Shell class). |
| **Memory store** | A persistent agent memory file/dir inventoried as a capability; out-of-band edits are flagged (attributed to a writing session or `unattributed`). |
| **Sandbox boundary** | Whether a call ran sandboxed (Claude Code has no signal yet → `unknown`); `oversight` reports % unsandboxed + denials by class. |
| **Legal hold** | A hold that survives retention, purge, and index rebuild; `purge` fails closed while held. |
| **Provenance / Agent Trace** | Mapping a commit/file/PR to the session that produced it; Cursor Agent Trace export validates against a pinned revision. |
| **Approval provenance v2** | The authorization taxonomy (`user`/`rule`/`classifier`/`auto`/`bypass`/`unknown`); no auto/bypass call is reported as `user`. |
| **Oversight** | The report of authorization mix, sessions by mode, human prompts, and a destructive×authorization cross-tab. |
| **Store-access** | A metadata-only record that a read/query (incl. MCP serve, pull) touched the store. |
| **Outcome fact** | A deterministic, non-scoring ratio/count (test/build/lint pass, retained/reverted, retries) with a derivation version. |
| **Incident case** | A named grouping of sessions with a merged, gap-annotated timeline and an offline-verifiable bundle (`agentwatch case`). |
| **Runner segment** | A sealed, self-verifying segment from an ephemeral/CI runner, imported with a `source: runner` chain-of-custody record. |
| **Evidence bundle** | A self-contained, offline-verifiable bundle (chain + coverage + privacy verdicts); re-verified with no store. |
| **ASI** | OWASP Top 10 for Agentic Applications (2026) + Agentic Skills Top 10; `compliance report --framework owasp-asi-2026`. |
| **CLI JSON contract** | The versioned `--json` schemas for the read/investigation commands (`schema/cli/v0.1.0/`), changelog-guarded. |
