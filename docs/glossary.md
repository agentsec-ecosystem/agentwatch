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
