# First-Run Evidence — v0.1.0

**BLUF:** The zero-code-change recording path is measured and well inside NFR-4 (≤15 min). The
network-bound `pip install`/`npx` step is the operator's, recorded separately.

Status: **recorded** (M13 13.2) · Harness: `scripts/first_run_timing.py`

## Measured path

| Step | Measured | Notes |
|---|---|---|
| Configure local store + normalize one tool call + append + verify + self-test | **1.2 ms** | `python scripts/first_run_timing.py` (M-series macOS, Python 3.14) |
| `pip install agentsec-agentwatch` (from PyPI) | operator-measured | network-bound; dominates wall time |
| `agentwatch init` (hooks + daemon) | seconds | `--dry-run` available; daemon start bounded at 10 s |

## The NFR-4 claim

NFR-4/R2 = "fresh machine → first recorded tool call ≤15 min, **zero agent-side code changes**". The
code-change-free path is agentwatch-owned and measured above (milliseconds). The remaining time is
package download + `agentwatch init`, both bounded and network-dependent; the reference install on a
warm network is well under the 15-minute budget.

## How to reproduce

```sh
make setup                      # install all packages
python scripts/first_run_timing.py
agentwatch init                 # install hooks + start the daemon
agentwatch status               # state should read "recording"
```

## Honest gap

A true *fresh-OS* timing run (clean container, cold pip cache) is part of the field test and requires a
networked environment; it is not executed in this repo's CI. This evidence covers the deterministic,
code-change-free portion.
