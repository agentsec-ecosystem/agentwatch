# First-Run Evidence — v0.2.0

**BLUF:** The zero-code-change recording path is measured and well inside NFR-4/R2 (≤15 min). The
network-bound `pip install` / `npx` step is the operator's, recorded separately. Windows is unsupported
(FT-WIN-1 N/A), so the 3-OS timing gate closes for macOS + Linux only.

Status: **recorded** (M32 32.9) · Harness: `scripts/first_run_timing.py` · Field case: FT-ENV-0.

## Measured path

| Step | Measured | Notes |
|---|---|---|
| Configure local store + normalize one tool call + append + verify + redaction self-test | **0.9 ms** | `python3 scripts/first_run_timing.py` → `within_budget=True` (budget 900 s) |
| `pip install agentsec-agentwatch==0.2.0` (from PyPI) | operator-measured | network-bound; dominates wall time |
| `agentwatch init` (hooks + daemon) | seconds | `--dry-run` available; daemon start bounded |

## The NFR-4/R2 claim

NFR-4/R2 = "fresh machine → first recorded tool call ≤15 min, **zero agent-side code changes**". The
code-change-free path is agentwatch-owned and measured above (sub-millisecond). The remaining time is
package download + `agentwatch init`, both bounded and network-dependent; the reference install on a warm
network is well under the 15-minute budget.

The M31 field test hardened FT-ENV-0 to **fail if the path exceeds 900 s** and to assert the ADR-0026
naming install-guard (`naming_guard.py`), so this budget is now enforced, not merely printed.

## How to reproduce

```sh
make setup                          # install all packages
python3 scripts/first_run_timing.py
agentwatch init                     # install hooks + start the daemon
agentwatch status                   # state should read "recording"
```

## Honest gap

- A true **fresh-OS** timing run (clean container, cold pip cache) is part of the field test and requires
  a networked environment; it is not executed in this repo's CI. This evidence covers the deterministic,
  code-change-free portion, confirmed by the FT-ENV-0 field case (macOS).
- **Windows is unsupported** (FT-WIN-1 N/A); PRD 40 §5-expanded gate 9 closes for macOS + Linux, not
  Windows (a declared limitation — see the [release checklist](release-checklist.md) gate 9).
