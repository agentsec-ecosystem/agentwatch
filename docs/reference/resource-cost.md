# Reference — Resource Cost to the Operator

**BLUF:** What agentwatch costs to run locally — CPU, memory, disk — so operators can size it.

## v0.1.0 (CLI + daemon)

| Resource | Estimate | Notes |
|---|---|---|
| CPU | <1% idle; small burst per tool call | async pipeline |
| Memory | ~30–60 MB (daemon) | Python + pydantic |
| Disk | ~1–10 MB/day (active user); 30-day retention 30–120 MB | under the 1024 MB cap |
| Network | 0 by default; export opt-in | R6 |

### Hook latency (measured)

Each Claude Code tool call spawns `agentwatch-hook`, which forwards one frame and exits 0
(fire-and-forget). Installed handlers use `"async": true`, so this does **not** block the agent's
tool-call path. The hook's own wall time (spawn → socket send → exit) is bounded by
`tests/test_hook.py::test_hook_latency_is_bounded` at **< 2 s**; a typical local run is well under
that. This is the honest number for the hook path — distinct from NFR-1's in-process SDK figure
(≤5 ms/step), which does not cover a process spawn.

### M12 measured bounds

- **Per-step (in-process, NFR-1):** adapter `normalize` and `Daemon.handle_message` p99 ≤ 5 ms
  (`tests/test_perf_budget.py`, `agentwatch.perf`).
- **Soak (NFR-7 groundwork):** 20k records stay within documented bounds for peak memory, chain
  verify time, and store size vs the cap (`scripts/soak.py`, nightly `soak.yml`).
- **Durability:** `store.durability` selects per-record / per-checkpoint / none fsync; `/healthz`
  reports the active mode. Default is per-record.
- **Logs:** `daemon.log` rotates at 5 MB × 2 backups (`agentwatch.rotating_log`), so it cannot grow
  unbounded.
- **File posture:** store dir `0700`, records/log/quarantine `0600` at creation (`agentwatch.posture`).

## v0.2.0+ (services stack)

- ~1–2 GB RAM with the full stack (Jaeger/Tempo + Postgres + API + analytics + web).
- Optional; v0.1.0 needs none of it.

## Cost in USD

Zero software cost (Apache-2.0). Operator cost is the machine overhead above; export egress to a paid
backend is the operator's choice.
