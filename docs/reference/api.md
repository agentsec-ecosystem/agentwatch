# Reference — Read API

**BLUF:** A FastAPI read surface over stored records and analytics. Shape preserved from the shipped project
(DD-12).

Status: **draft**.

| Endpoint | Purpose |
|---|---|
| `GET /api/runs` | Run list with filtering (agent, version, workload) |
| `GET /api/runs/{id}` | Single run timeline (span tree + anomalies) |
| `GET /api/fleet` | Fleet health rollups (agents, versions, workloads) |
| `GET /api/compare` | Version-to-version deltas (cost, retry rate, success, tool usage) |
| `GET /api/anomalies` | Anomaly inbox with type/severity/agent filters |

OpenAPI document to be generated and published at release. Contract tests guard the shapes listed above.
