# Dependency & License Review — v0.2.0

M32 item **32.6** (issue #414). Rule: **no new runtime dependency without a decision**, and
[`THIRD_PARTY_NOTICES.md`](../../../THIRD_PARTY_NOTICES.md) must be current.

## Runtime dependencies

| Package | Runtime dependencies | License(s) | Decision |
|---|---|---|---|
| `packages/python-sdk` | `opentelemetry-api`, `opentelemetry-sdk`, `tomli` (py<3.11) | Apache-2.0, MIT | unchanged since v0.1.0 |
| `services/api` | `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `asyncpg`, `httpx`, `opentelemetry-api/sdk` | MIT, BSD-3-Clause, Apache-2.0 | unchanged since v0.1.0 |
| `services/analytics` | `opentelemetry-api/sdk`, `httpx`, `asyncpg`, `pydantic`, `pydantic-settings`, `click`, `alembic`, `openai` | Apache-2.0, BSD-3-Clause, MIT | unchanged since v0.1.0 |
| `packages/cli` (npm) | none | — | no runtime deps |

Every runtime dependency is under a **permissive** license (Apache-2.0 / MIT / BSD-3-Clause) — no copyleft.

## Changes in v0.2.0

- **No new base runtime dependency.**
- One **optional extra**: `packages/python-sdk` `[codex]` → **`zstandard>=0.22; python_version < '3.14'`**
  (BSD-3-Clause). Decision: Codex rollout logs may be `.jsonl.zst`; Python 3.14+ has `compression.zstd` in the
  **stdlib**, so this is only needed on older interpreters. The preference order is implemented in
  `agentwatch/codex_rollout.py` (`compression.zstd` first, then `zstandard`) and recorded in
  `pyproject.toml` (M27 COD-1). Permissive; opt-in.

## Checks

| Check | Result | Evidence |
|---|---|---|
| Known vulnerabilities | ✅ 0 | `make security-scan` → [`security-scan/pip-audit-*.json`](security-scan/) (python-sdk, api, analytics) |
| No egress-capable runtime imports | ✅ | `scripts/dependency_egress_audit.py`; `tests/test_egress_audit.py` |
| All licenses permissive | ✅ | table above |
| `THIRD_PARTY_NOTICES.md` current | ✅ | covers the ported predecessor (`agent-exec-trace`, MIT) and the cross-harness test-kit corpus (MIT, with `PROVENANCE.md` + content-addressed lock) |

**No new runtime dependency without a decision: satisfied.** `THIRD_PARTY_NOTICES.md` is current.

## Reproduce

```bash
make security-scan     # pip-audit per package + egress audit
```
