# Runbook — Tamper Response

Goal: respond when agentwatch reports a tamper/tampering signal (config edit or store break).

## Symptoms

- Hash-chain verification failure.
- Hook config changed unexpectedly.
- Recording stopped without an operator action.

## Steps

1. Do **not** overwrite the store; preserve it as evidence.
2. Verify the chain: `agentwatch verify-store` (reports the first broken link).
3. Compare hook/daemon config against the last known-good state.
4. Re-enable recording (fail-closed) and capture a snapshot before repair.
5. Report via the org security policy if a malicious tamper is suspected.

## Principle

agentwatch fails **closed**, and a recording gap is surfaced — never silent (NFR-8/12).
