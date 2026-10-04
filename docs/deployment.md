# Deployment

**BLUF:** agentwatch is local-first. v0.1.0 is a CLI + daemon; the service stack (API, analytics, web,
collector, Jaeger/Tempo, Postgres) is for v0.2.0+ and runs via Docker Compose.

## v0.1.0

- CLI + local daemon only; no services required.
- Store: local JSONL + hash chain (`DD-08`).

## v0.2.0+ local stack

```sh
docker compose up -d     # jaeger/tempo, otel-collector, postgres, api, analytics, web
```

| Service | Port (default) | Purpose |
|---|---|---|
| OTLP collector | 4317 | ingest |
| Jaeger/Tempo | 16686 | trace store |
| API | 8000 | read API |
| Web | 5173 | operator UI |
| Postgres | 5432 | analytics |

See [runbooks/deploy-local-stack.md](runbooks/deploy-local-stack.md). Production is out of scope for v1.
