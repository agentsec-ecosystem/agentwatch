# agentwatch — Design Decisions

Centralized decision log. Referenced as `DD-NN`. Status is **proposed** until confirmed during the
v0.1.0 build.

| ID | Decision | Status | Rationale |
|---|---|---|---|
| DD-01 | **Core runtime:** Python core (SDK + analytics service + API) for true shipped-feature parity; `npx @agentsec-ecosystem/cli` is a thin launcher that installs/invokes the Python CLI; the CLI is also published on PyPI | **accepted** (2026-10-02) | Parity with the shipped `agent-exec-trace` Python SDK/services; preserves existing instrumentation and read-API contracts. See PRD 10 §D–§E |
| DD-02 | Record format = OTel GenAI spans (`execute_tool`) + a versioned security-event schema | proposed | Standards alignment; portability; schema is the differentiator |
| DD-03 | Local-first storage; export opt-in via OTLP | proposed | Privacy by default (R6) |
| DD-04 | Adapter boundary as an explicit contract; Claude Code hooks are the first implementation | proposed | Harness-agnostic by construction (R3) |
| DD-05 | Contribute schema improvements upstream to OTel GenAI; do not fork | proposed | Adoption > control |
| DD-06 | Redaction happens at normalization time, before storage | proposed | Never persist secrets (R7) |
| DD-07 | Storage hash-chained for tamper evidence | proposed | Forensic trust (R11) |

## Template

```
### DD-NN — Title
- **Status:** proposed | accepted | superseded
- **Context:**
- **Decision:**
- **Consequences:**
```
