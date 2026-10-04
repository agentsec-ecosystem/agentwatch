# Design — Recorder Attack Matrix

**BLUF:** agentwatch observes an agent that runs on the same machine, as the same user, with shell
access. This is the published result of the **anti-forensics suite** (M16 S30, PRD 32): what an on-box
attacker can do to the recorder, what agentwatch detects after the fact, what it prevents, and which
command evidences each row. It is threat-model test evidence, not a how-to; every "not preventable" row
is paired with the detection that covers it.

**Scope:** the recorder's own fault-injection suite (`tests/test_anti_forensics.py`), extending F1–F10
from "things that break" to "things broken on purpose." It is deliberately **not** agentdrill: no attack
packs against the agent, no evals.

**Status:** published (v0.1.0). Sources: [PRD 32](../prd/32-coverage-and-recorder-trust.md),
[threat model](threat-model.md), [PRD 06](../prd/06-security-baseline.md), PRD 28.

## The matrix

| Scenario | Preventable | Detectable after the fact | Command / evidence | Compensating control (when neither) |
|---|---|---|---|---|
| **Kill the daemon** mid-session | No (same-user kill) | **Yes** | `recording-gap` record on restart; `doctor`, `coverage` (`gap:daemon-down`), `/healthz` | — |
| **Truncate** the store / append garbage | No (same-user write); file posture reduces | **Yes** | `verify-store` reports the chain break; `/healthz` goes `stopped` | — |
| **Strip hooks** from `settings.local.json` | No; file perms (PRD 28) only raise cost | **Yes** | `status` / `doctor` show hooks absent | A silent edit leaves no chain record; S5 marks a *deliberate* `uninstall` |
| **Exhaust disk** (trip the size cap) | **Yes** — recording fails closed at the cap, never overwrites (F3) | **Yes** | `doctor` `store-disk`; `/healthz` `stopped` with the cap reason | — |
| **Hold the socket** | No; owner-only socket raises cost | **Yes** | A second daemon refuses to start; a hook send fails and the frame is spooled (F1) | — |
| **Move the store** | No | **No** — the old path verifies as a clean, empty chain | `coverage` (`gap:*`) compares transcript ground truth to the empty store | S2 coverage + S5 windows; the chain alone cannot tell |
| **Skew the clock** (future-dated events) | No | **Yes** | F9 flag; `doctor`; `/healthz` `clock_skew_s` and `degraded` | — |
| **Replay stale frames** | No | **Partial** — deduplicated within one daemon session; a restart re-appends | `verify-store` proves append order, not origin | S1 evidence bundle timestamps; cross-restart replay is *neither* |

## How to read a row

- **Preventable** — the recorder stops the harm (e.g. the size cap refuses to overwrite).
- **Detectable after the fact** — a command names the damage; the row names it explicitly.
- **Neither** — no detection from the chain alone; the compensating control says what still covers it.

## What the recorder does *not* claim

- It does not prevent a same-user on-box attacker; it makes their actions **visible and attributable**.
- A store moved away looks clean-but-empty to `verify-store`; only `coverage` (transcripts vs store)
  surfaces the missing range.
- A stale frame replayed after a daemon restart appends again; the chain proves ordering, not origin.
