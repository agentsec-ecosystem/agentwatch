# PRD 04 — Users and CUJs

**BLUF:** Primary users are platform/security engineers who need proof of what agents did before they
trust any enforcement. Personas align with the ecosystem research base (P1 Maya, P2 Ravi, P4 Sam).

## Users

- **P1 Maya — platform engineer** — installs agentwatch, exports traces to a backend the team already owns.
- **P2 Ravi — security engineer** — needs a defensible audit trail and the security-event schema.
- **P4 Sam — solo developer** — wants a local audit trail with near-zero setup.

## Critical user journeys (v0.1.0)

1. **Install & record** — fresh machine → `agentsec init` → first Claude Code tool call recorded in ≤15 min, zero agent-side code changes.
2. **Replay** — given a session id, reconstruct the ordered action timeline for forensics.
3. **Export** — send records to a standard OTel backend unmodified.
4. **Emit a security event** — a policy/deny/secret event is emitted in the named schema (from agentpolicy/agentdrill).
