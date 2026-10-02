# Reference — Resource Cost to the Operator

**BLUF:** What agentwatch costs to run locally — CPU, memory, disk — so operators can size it.

## v0.1.0 (CLI + daemon)

| Resource | Estimate | Notes |
|---|---|---|
| CPU | <1% idle; small burst per tool call | async pipeline |
| Memory | ~30–60 MB (daemon) | Python + pydantic |
| Disk | ~1–10 MB/day (active user); 30-day retention 30–120 MB | under the 1024 MB cap |
| Network | 0 by default; export opt-in | R6 |

## v0.2.0+ (services stack)

- ~1–2 GB RAM with the full stack (Jaeger/Tempo + Postgres + API + analytics + web).
- Optional; v0.1.0 needs none of it.

## Cost in USD

Zero software cost (Apache-2.0). Operator cost is the machine overhead above; export egress to a paid
backend is the operator's choice.
