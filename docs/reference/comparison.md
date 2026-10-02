# Reference — Comparison

**BLUF:** How agentwatch differs from adjacent tools. We record agent **behavior + security events**
locally and openly; others do calls, scans, or hosted analytics.

| | agentwatch | LLM observability (LangSmith/LangFuse/Phoenix) | Hosted agent observability (e.g. Explorer) | MCP/agent scanners (agent-scan) |
|---|---|---|---|---|
| Unit recorded | agent behavior + security events | individual LLM calls | traces (hosted) | static config/content |
| Security-event schema | ✅ open, versioned | ✗ | ✗ | ✗ |
| Local-first / no egress | ✅ | varies | ✗ | ✅ |
| Coding-agent coverage | ✅ (Claude Code first) | varies | varies | ✗ |
| Detectors | ✅ 40 | partial | ✅ | ✗ |
| Open license | Apache-2.0 | OSS/varies | proprietary | OSS |
| Enforcement | ✗ (agentpolicy) | ✗ | ✗ | ✗ |
