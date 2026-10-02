# User Guide

**BLUF:** How to run agentwatch day to day: install, confirm recording, investigate a session, compare
versions, and handle anomalies.

## Install & record

```sh
npx @agentsec-ecosystem/cli init     # or: pipx run agentwatch init
agentwatch status                    # confirm recording (monitor-only default)
```

## Investigate

```sh
agentwatch sessions                  # list recorded sessions
agentwatch replay <session-id>       # ordered action timeline
```

## Compare versions

The **Version Compare** view shows side-by-side deltas (cost, retry rate, success rate, tool usage) between
two agent versions.

## Anomalies

The **Anomaly Inbox** lists flagged runs by severity/type/agent, each with an explanation and evidence
payload. Use it as a triage queue; enforcement decisions belong to agentpolicy.

## Export (optional)

```sh
agentwatch export enable --otlp-endpoint http://localhost:4317
```

Export is blocked until the redaction self-test passes. See
[runbooks/export-to-otel.md](runbooks/export-to-otel.md).

## Troubleshooting

- No session recorded → check hooks + daemon; recording must not be silent.
- Unexpected gap → see [runbooks/tamper-response.md](runbooks/tamper-response.md).
