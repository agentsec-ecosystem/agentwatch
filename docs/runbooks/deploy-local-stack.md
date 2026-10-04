# Runbook — Deploy the Local Stack (v0.2.0+)

```sh
docker compose up -d
docker compose ps
```

## Verify

- [ ] Collector healthy on `:4317`.
- [ ] API responds on `/api/fleet`.
- [ ] Web loads on `:5173`.
- [ ] Seed: `make seed-e2e` (96 runs, ~240 anomalies).

## Troubleshoot

- Postgres not ready → check volume/permissions.
- No traces in Jaeger → check the collector endpoint in `AgentTracer.setup`.
