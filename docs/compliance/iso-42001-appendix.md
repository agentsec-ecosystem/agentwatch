# ISO/IEC 42001:2023 AI management-system appendix

> A controls-mapping aid for an AI management system (AIMS), not a certification.
> Every row names an evidence command that exists.

| Clause / control area | agentwatch feature | Evidence |
|---|---|---|
| Operational planning and control — traceability | Append-only, hash-chained activity records | `agentwatch verify-store` |
| AI system lifecycle — logging and monitoring | Session boundaries, behavior records, drift signals | `agentwatch sessions`, `agentwatch drift` |
| Data for AI systems — minimization | Redaction before storage; metadata-only default | `agentwatch verify-privacy` |
| Transparency and explainability of records | Layered config explanation; deterministic, LLM-free transforms | `agentwatch config explain` |
| Third-party / supply-chain (tools, MCP) | Agent + MCP inventory; tool-surface drift | `agentwatch inventory`, `agentwatch inventory --diff` |
| Incident management — evidence | Self-contained, verifiable evidence bundle | `agentwatch evidence <id>` |
| Continual improvement | Coverage reconciliation names gaps instead of hiding them | `agentwatch coverage` |

## Not applicable / elsewhere

| Area | Note |
|---|---|
| AI risk assessment | Out of scope; agentwatch supplies evidence to the process |
| Conformity / certification | agentwatch does not certify; it is a mechanism |
