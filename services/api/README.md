# agentwatch-api

Read API service for `agentwatch` — serves product-facing views (run timeline, fleet health, version compare, anomaly inbox) from the normalized Postgres read model.

## Installation

```bash
pip install agentwatch-api
```

Published on [PyPI](https://pypi.org/project/agentwatch-api/).

Run with:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

See the [top-level README](../README.md) and [docs/reference/configuration.md](../docs/reference/configuration.md) for installation and configuration.

## License

MIT — see [LICENSE](../LICENSE).