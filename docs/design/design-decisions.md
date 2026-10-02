# agentwatch — Design Decisions

Centralized decision log. Referenced as `DD-NN`. Status is **proposed** until confirmed during the
v0.1.0 build.

| ID | Decision | Status | Rationale |
|---|---|---|---|
| DD-01 | **Core runtime:** preserve a Python-compatible core (SDK + analytics + API) for shipped-feature parity, with a thin launcher for `npx @agentsec-ecosystem/cli` | proposed | Parity with the shipped `agent-exec-trace` Python SDK/services; avoids breaking existing instrumentation. See PRD 10 §E |
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
