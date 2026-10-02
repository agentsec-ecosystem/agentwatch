# PRD 01 — Why

**BLUF:** Every harness keeps agent telemetry in its own console, so incident forensics and compliance
both fail on the same gap: *no complete, exportable record of what the agent did.* agentwatch provides
that record in OpenTelemetry GenAI format, and defines the security-event schema the whole ecosystem
emits.

## Problem

1. No harness ships complete, exportable, vendor-neutral audit trails of agent tool calls.
2. OTel GenAI semantic conventions exist but are Development-grade, with no "just works" implementation.
3. No standard security-event semantics (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`)
   exist at all.
4. Incident postmortems (Replit, Plugin4Shell) and compliance both died on the same line: "we had no
   record of what the agent did."

## Why now

Agents hold shell, filesystem, credential, and tool access — and the incident record is real and growing.
Recording is the prerequisite for every other capability (alert, block, revoke).
