# CLI JSON contract (v0.1.0)

The machine-readable contract for the read/investigation commands' `--json`
output. Agent tools (and the shipped `investigation` skill) read this to parse
results without guessing; a breaking change is a new versioned directory, never
an in-place edit.

## Layout

```
schema/cli/
  CHANGELOG.md          # every version an entry; the guard fails without it
  README.md             # this file
  v0.1.0/               # the current published version
    search.schema.json  # one record object per line (NDJSON)
    replay.schema.json  # array of {record}
    impact.schema.json
    blame.schema.json
    coverage.schema.json
    cost.schema.json
    oversight.schema.json
    inventory.schema.json
    diff.schema.json
    trace.schema.json
    tree.schema.json
    flow.schema.json
    secrets.schema.json
```

Each schema carries `x-agentwatch-command` and `x-agentwatch-cli-version` and a
resolvable `$id`.

## Stewardship

`agentwatch.cli_schema.check_cli_schemas` is the guard (same pattern as
`schema/GOVERNANCE.md`): a registered read command without a schema fails, a
schema for an unregistered command fails, a schema whose `type` disagrees with
its output kind fails, and the changelog must name **v0.1.0**. To add a command
or change a shape: add/extend the schema **and** the `CHANGELOG.md` entry in the
same change, and bump `CLI_SCHEMA_VERSION` for anything non-additive.

## Scope

This covers the **CLI** JSON contract for the investigation workflow; the HTTP
contract is PRD 46 API-1. The record payload itself is governed by
[`schema/agent-record.schema.json`](../agent-record.schema.json).
