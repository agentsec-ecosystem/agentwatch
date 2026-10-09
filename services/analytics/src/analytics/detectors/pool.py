"""Scripted asyncpg-like pool for offline baseline/cohort detector evaluation.

Baseline detectors (cost/duration/intervention/output/cross-run) query Postgres
through an ``asyncpg`` pool. Offline evaluation drives them with this scripted
pool, whose ``fetchrow``/``fetch`` return preset values per SQL shape — no live
database. Kept dependency-free and shared by the scenario runner and the public
corpus so both use one implementation.
"""

from __future__ import annotations

from typing import Any


class _Conn:
    def __init__(self, values: dict[str, Any]) -> None:
        self.v = values

    async def fetchrow(self, sql: str, *a: Any) -> dict[str, Any] | None:
        s = sql.lower()
        if "avg(estimated_cost)" in s:
            return {"avg_cost": self.v.get("avg_cost")}
        if "avg(duration_ms)" in s:
            return {"avg_dur": self.v.get("avg_dur")}
        if "avg(total_interventions)" in s:
            return {"avg_int": self.v.get("avg_int")}
        if "avg(length" in s:
            return {"avg_len": self.v.get("avg_len")}
        if "count(*)" in s and "run_summaries" in s:
            return {"cnt": self.v.get("cnt", 0), "first_run": self.v.get("first_run")}
        return None

    async def fetch(self, sql: str, *a: Any) -> list[dict[str, Any]]:
        if "from anomalies" in sql.lower():
            return [{"anomaly_type": t} for t in self.v.get("anomaly_types", [])]
        return []


class _Acq:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _Conn:
        return self.conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class ScriptedPool:
    """A minimal asyncpg-like pool whose queries return preset values."""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.conn = _Conn(values or {})

    def acquire(self) -> _Acq:
        return _Acq(self.conn)


__all__ = ["ScriptedPool"]
