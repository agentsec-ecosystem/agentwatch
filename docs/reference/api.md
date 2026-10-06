# Reference — Read API

**BLUF:** A FastAPI read surface over stored records and analytics. Shape preserved from the shipped project
(DD-12).

Status: **draft**.

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Health/readiness (DB reachable) |
| `GET /api/v1/runs/{run_id}` | Single run timeline (span tree + anomalies) |
| `GET /api/v1/fleet` | Fleet health rollups (agents, versions, workloads) |
| `GET /api/v1/compare` | Version-to-version deltas (cost, retry rate, success, tool usage) |
| `GET /api/v1/anomalies` | Anomaly inbox with type/severity/agent filters |

## Published contract (M26 API-1)

The FastAPI app is the single source of truth. [`openapi.json`](../../services/api/openapi.json) and the typed
client [`api.client.AgentwatchClient`](../../services/api/src/api/client.py) are generated together by
`scripts/generate_openapi.py`:

```sh
python scripts/generate_openapi.py          # regenerate openapi.json + client.py
python scripts/generate_openapi.py --check  # CI drift check
```

`services/api/tests/test_openapi_contract.py` regenerates both and fails on drift, and asserts the client exposes
exactly one method per OpenAPI operation.
