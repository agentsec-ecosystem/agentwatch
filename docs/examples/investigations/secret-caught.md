# The secret that never hit disk

**The question:** a key was used in a command — is it in the store?

Seed the store and find the session:

```sh run
export DEMO_STORE="${DEMO_STORE:-/tmp/agentwatch-demo}"
python3 scripts/seed-investigations.py --store "$DEMO_STORE"
agentwatch --set store.path="$DEMO_STORE" search --session sess-secret
```

The record shows a `Bash` call whose arguments are already redacted
(`<REDACTED:api-key>`), plus a `secret_detected` security event. The raw value
was never written — redaction happens **before storage** (DD-06).

Prove the store is clean:

```sh run
agentwatch --set store.path="$DEMO_STORE" verify-privacy
```

`verify-privacy` re-scans stored records for secret patterns and known leak
shapes and exits non-zero if it finds any. Here it passes.

**What to look for:** a `security_event` with `type: secret_detected` and an
arguments payload that contains only the redaction placeholder. If you ever see
the real value, `verify-privacy` fails loudly — never silently.

See also: the redaction rules in [`docs/prd/16-configuration.md`](../../prd/16-configuration.md)
and the capture-fidelity contract in [`docs/prd/25-capture-fidelity.md`](../../prd/25-capture-fidelity.md).
