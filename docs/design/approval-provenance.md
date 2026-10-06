# Design — Approval Provenance

**BLUF:** The record says **who authorized a tool call** — `user`, `auto`, `not-required`, `denied`,
or `unknown` — derived from the permission surface the harness actually exposes. Where the harness
cannot prove the difference between a human approval and an allow-list auto-approval, the value is
`unknown`, never guessed. A guessed consent is a false audit record, which is worse than no field.

> **Superseded for new work (v0.2.0-expanded):** this five-value field predates auto mode (model-classifier approvals)
> and bypass-as-default. New capture uses the **authorization source taxonomy v2** in
> [`authorization-provenance-v2.md`](authorization-provenance-v2.md) ([PRD 49](../prd/49-authorization-and-oversight.md)).
> The table below is retained for **historical records only** and as the S14 legacy mapping.

**Status:** published (v0.1.0) · **Milestone:** M19 · Sources: [PRD 35](../prd/35-capture-context.md)
§S14, [PRD 14](../prd/14-non-goals.md), [record-format spec](../reference/record-format-spec.md).

## Why a field, not a verdict

`outcome=ok` silently merges three different facts: *a human approved `rm -rf`*, *an allow-list
auto-approved it*, and *it needed no permission*. The first question about a destructive action is
"did a human say yes?", and `denied` records only refusals. `approval` records the consent.

It is **observation only**: agentwatch records the authorization decision; it never makes one. There
is no allow/deny hook, no policy, no block.

## Values

| Value | Meaning |
|---|---|
| `user` | A human explicitly approved the call (a permission prompt preceded it). |
| `auto` | An allow-list / settings rule auto-approved it. |
| `not-required` | The call needed no permission. |
| `denied` | The harness refused it. |
| `unknown` | The harness did not expose enough to decide — the default. |

The field is **absent** on records where the derivation has no evidence; `effective_approval` reads
absence as `unknown`, so new and legacy records behave identically. The value is never written back
silently.

## Per-harness derivation (claude-code)

First match wins:

1. a `PermissionDenied` event → `denied`;
2. an explicit `approval` field on the event (a harness passthrough) → that value;
3. a matching `Notification` permission prompt (same `tool_use_id`) → `user`;
4. `permission_decision: allow` with `permission_source` in `{allowlist, settings, config, auto}`
   → `auto`;
5. `permission_required: false` → `not-required`;
6. otherwise → `unknown` — we never infer consent from `outcome=ok`.

The `Notification` hook fires on a permission prompt; the daemon remembers the prompt by
`tool_use_id` and stamps the following `PreToolUse` as `user`. An `allow` decision with no source is
**ambiguous** and stays `unknown` (it could be a human or a rule). The table is published here and
versioned with the adapter.

## Surfacing

`agentwatch search --approval user`, the `replay`/`view` timeline (an `approval=` suffix when set),
the evidence bundle (via the record's JSON), and impact analysis all read the same field.

## Privacy

Approval is a property of the authorization decision, not the argument content: it is safe under every
privacy mode and adds no new content to the store.
