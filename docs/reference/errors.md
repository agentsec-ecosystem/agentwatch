# Reference — Error Contract (v0.1.0)

**BLUF:** Every `agentwatch` CLI failure emits exactly **one** machine-readable JSON envelope on
stderr, with a stable `code`, a human `message`, a `hint`, and a `doc_url`. The exit-code table below
is generated from `agentwatch.errors` ([PRD 38 §Q8](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/prd/38-engineering-rigor.md)).

Errors are a published contract, like the [store format](store-format.md): a script (CI, a launcher, a
community wrapper) can branch on `error.code` instead of scraping prose. Human-facing output is still
printed first; the envelope is the final line on stderr.

## Envelope

```json
{"error": {"code": "E_CONFIG", "message": "configuration error: unknown key 'store.nope'", "hint": "Fix or remove the reported key/value; configuration is strict.", "doc_url": "https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/reference/errors.md#e-config"}}
```

| Field | Meaning |
|---|---|
| `code` | Stable identifier; add-only within a major. Branch on this. |
| `message` | Human-readable description of what failed. |
| `hint` | The next thing to try. |
| `doc_url` | Anchored link into this page. |

The envelope is emitted for usage errors, configuration errors, install/lifecycle failures,
unimplemented commands, a broken store chain, a missing session, an unreachable daemon, a refused
destructive action, invalid input, and unexpected internal failures. There is exactly one envelope per
failed invocation and none on success.

## Exit codes

Codes map deterministically to process exit statuses. `0` is success; the nonzero statuses are the
distinct values below (`1`, `2`, `3`).

<!-- BEGIN GENERATED: exit-codes -->
| Code | Exit | Meaning | Hint |
|---|---|---|---|
| `E_USAGE` | `2` | Bad arguments or an unknown subcommand/flag (argparse usage error). | Run `agentwatch <command> --help` and re-run. |
| `E_CONFIG` | `2` | Configuration is invalid, unknown, or missing an explicit `--config` file (fail-closed). | Fix or remove the reported key/value; configuration is strict. |
| `E_INSTALL` | `1` | install/hook/daemon lifecycle failed, or a check ran and failed. | Run `agentwatch doctor` for the failing check. |
| `E_NOT_IMPLEMENTED` | `3` | The subcommand is wired but not implemented in this milestone. | See the WBS for the milestone that lands it. |
| `E_CHAIN_BROKEN` | `1` | The store hash chain did not verify. | Run `agentwatch sessions --check` or `agentwatch verify-store` for the break. |
| `E_SESSION_NOT_FOUND` | `1` | No records exist for the requested session. | Run `agentwatch sessions` to list recorded sessions. |
| `E_DAEMON_UNREACHABLE` | `1` | The daemon could not be reached. | Run `agentwatch init` or `agentwatch status` to check the daemon. |
| `E_CONFIRMATION_REQUIRED` | `1` | A destructive action was refused without confirmation. | Re-run with `--yes` if the action is intended. |
| `E_NO_TRANSCRIPTS` | `1` | No transcripts were found to import. | Pass an explicit path or check the source directory. |
| `E_NO_SOURCES` | `1` | No sources were found to ingest. | Pass an explicit path or check the source directory. |
| `E_INVALID_INPUT` | `1` | Input (a record, event, or option value) was invalid. | Check the reported field and retry. |
| `E_FAILED` | `1` | The command failed without a more specific code. | Re-run with more context or check the message. |
| `E_INTERNAL` | `1` | An unexpected internal error occurred. | Re-run; if it persists, report it with the command and message. |
<!-- END GENERATED: exit-codes -->

## Stability

- **Adding** a code is a compatible change (a consumer's `else` branch already covers it).
- **Removing or renaming** a code, or changing its exit status, is a breaking change and follows the
  major/deprecation policy in [PRD 38 §Q7](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/prd/38-engineering-rigor.md).
- The catalog in `agentwatch.errors` is the single source of truth; the table above is generated from it
  and checked in CI (`packages/python-sdk/tests/test_error_contract.py`), so it cannot drift.
