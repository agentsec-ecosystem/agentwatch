# ADR-0030 — Hook transport & end-to-end wall-clock budget

- **Status:** accepted (2026-10-06, M29 DEP-3)
- **Decision:** the published, user-visible budget is the **end-to-end hook
  wall-clock** (a fresh interpreter process per hook, two per tool call), gated
  in CI per OS via `scripts/hook_perf_gate.py` (`.github/workflows/hook-perf.yml`)
  with a committed per-OS baseline and a drift band. `reference/performance.md`
  states it in user terms (`< 500 ms per tool call at p99`) plus a 500-call
  session overhead quote. The default transport stays the Unix domain socket;
  no transport change is made before this measurement (D-51).
- **Consequences:** a regression beyond the budget or the drift band fails CI; a
  missed budget is a tracked decision (this ADR), never a silent miss. The
  in-process NFR-1 (≤5 ms/step) budget remains absolute and unchanged.
- **Blocked:** the Windows end-to-end number is blocked on WIN-1 (named-pipe
  transport re-pointed to M31); Windows is reported blocked, not measured. The
  Linux row is pending an `ubuntu-latest` CI run.
- **Evidence:** `agentwatch.hook_perf`; `scripts/hook_perf_gate.py`;
  `tests/test_hook_wallclock.py`.