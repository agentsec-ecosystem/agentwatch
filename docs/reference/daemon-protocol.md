# Reference — Daemon Socket Protocol (v0.1.0)

**BLUF:** The local daemon accepts newline-delimited JSON **frames** over an owner-only Unix domain
socket. This is a **published contract**: the hook client and any sibling tool (agentpolicy, agentkeys,
agenthalt) send frames to it.

Status: **experimental** (v0.1.0). Compatibility: additive (new phases), breaking major + deprecation.
Contract version: `agentwatch.protocol.PROTOCOL_VERSION` (currently `0.1.0`).

## Socket

Resolved by `agentwatch.hook.default_socket_path()`: `$AGENTWATCH_SOCKET`, else `$XDG_RUNTIME_DIR/agentwatch.sock`,
else `/tmp/agentwatch.sock`. The socket is owner-only (`0600`); no authentication beyond filesystem
permissions. Multi-user access is out of scope (fleet is v0.1.x).

## Frame

One JSON object per line:

```json
{"phase": "pre", "harness": "claude-code", "event": { … }}
```

Keys are fixed: `phase`, `harness`, `event` (`agentwatch.protocol.FRAME_KEYS`).

## Phases

`agentwatch.protocol.FRAME_PHASES`:

| Phase | Meaning |
|---|---|
| `pre` | tool-use intent |
| `post` | tool-use outcome |
| `denied` | harness-native permission denial |
| `prompt` | user prompt (opening reason step) |
| `session-start` / `session-end` | session boundary (`resume`/`fork` link a parent) |
| `hook-error` | malformed hook input, recorded not dropped (F2) |
| `event` | a validated security event emitted by a sibling tool |

An unknown phase is rejected explicitly by the adapter, never dropped silently.

## Delivery

The hook is fire-and-forget (always exits 0). If the daemon is unreachable the frame is spooled and
delivered late, never lost.

## Pinned by

`packages/python-sdk/tests/test_protocol_contract.py` (frame keys + phases), `tests/test_hook.py`,
`tests/test_daemon.py`.
