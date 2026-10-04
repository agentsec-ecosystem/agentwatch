"""Coverage for API helper, DB-pool, lifespan, and query-filter branches (WBS M0 0.T).

The shipped suite left these branches unexercised (91% coverage, confirmed
against the ported source), which is below the agentwatch ≥95% gate. These are
characterization tests: they pin existing behavior, they do not change it.
"""

from __future__ import annotations

import runpy
import warnings
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

import api.db as db
from api import main, queries
from api.main import app


def _mock_pool(rows: list[dict[str, Any]] | None = None) -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=rows or [])
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = Mock(return_value=acquire_cm)
    return pool


# ── _to_float ─────────────────────────────────────────────────────────────────


def test_to_float_none() -> None:
    assert queries._to_float(None) is None


def test_to_float_decimal() -> None:
    assert queries._to_float(Decimal("1.50")) == 1.5


def test_to_float_int_and_float() -> None:
    assert queries._to_float(3) == 3.0
    assert queries._to_float(2.5) == 2.5


def test_to_float_numeric_string() -> None:
    assert queries._to_float("4.25") == 4.25


def test_to_float_unparsable_string() -> None:
    assert queries._to_float("not-a-number") is None


def test_to_float_other_type() -> None:
    assert queries._to_float(object()) is None


# ── _to_int ───────────────────────────────────────────────────────────────────


def test_to_int_none_returns_default() -> None:
    assert queries._to_int(None) == 0
    assert queries._to_int(None, 7) == 7


def test_to_int_int() -> None:
    assert queries._to_int(5) == 5


def test_to_int_decimal_truncates() -> None:
    assert queries._to_int(Decimal("3.9")) == 3


def test_to_int_numeric_string() -> None:
    assert queries._to_int("12") == 12


def test_to_int_unparsable_string_returns_default() -> None:
    assert queries._to_int("x", 4) == 4


def test_to_int_other_type_returns_default() -> None:
    assert queries._to_int(["a"], 2) == 2


# ── _parse_json_object ────────────────────────────────────────────────────────


def test_parse_json_object_dict_passthrough() -> None:
    value = {"a": 1}
    assert queries._parse_json_object(value) is value


def test_parse_json_object_json_string() -> None:
    assert queries._parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_bad_json() -> None:
    assert queries._parse_json_object("{not json") is None


def test_parse_json_object_json_non_dict() -> None:
    assert queries._parse_json_object("[1, 2]") is None


def test_parse_json_object_non_string() -> None:
    assert queries._parse_json_object(None) is None
    assert queries._parse_json_object(42) is None


# ── query filters ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fleet_rollups_covers_workload_filter() -> None:
    _rows, total = await queries.get_fleet_rollups(_mock_pool(), workload_type="code-review")

    assert total == 1


@pytest.mark.asyncio
async def test_get_anomalies_covers_agent_filter() -> None:
    _rows, total = await queries.get_anomalies(_mock_pool(), agent_name="demo-agent")

    assert total == 1


# ── build_version_compare branches ────────────────────────────────────────────


def test_build_version_compare_neither_cohort() -> None:
    result = queries.build_version_compare(None, None, "v1", "v2")

    assert result["warning"] == "sparse_cohorts"
    assert result["note"] == "Neither version cohort was found"


def test_build_version_compare_left_missing() -> None:
    result = queries.build_version_compare(None, {"total_runs": 10}, "v1", "v2")

    assert result["note"] == "Left version 'v1' not found"


def test_build_version_compare_right_missing() -> None:
    result = queries.build_version_compare({"total_runs": 10}, None, "v1", "v2")

    assert result["note"] == "Right version 'v2' not found"


# ── DB pool lifecycle ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_pool_creates_pool_once(monkeypatch: pytest.MonkeyPatch) -> None:
    created = object()
    monkeypatch.setattr(db, "_pool", None)
    with patch("api.db.asyncpg.create_pool", new=AsyncMock(return_value=created)) as create:
        first = await db.get_pool()
        second = await db.get_pool()

    assert first is created
    assert second is created
    create.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_pool_closes_and_resets(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    monkeypatch.setattr(db, "_pool", pool)

    await db.close_pool()

    pool.close.assert_awaited_once()
    assert db._pool is None


# ── app lifespan + entry point ────────────────────────────────────────────────


def test_lifespan_reports_healthy_database() -> None:
    with (
        patch("api.main.get_pool", new=AsyncMock(return_value=object())),
        patch("api.main.health_check", new=AsyncMock(return_value=True)),
        patch("api.main.close_pool", new=AsyncMock()) as close,
        TestClient(app),
    ):
        pass

    close.assert_awaited_once()


def test_lifespan_warns_when_database_unavailable() -> None:
    with (
        patch("api.main.get_pool", new=AsyncMock(return_value=object())),
        patch("api.main.health_check", new=AsyncMock(return_value=False)),
        patch("api.main.close_pool", new=AsyncMock()),
        patch("api.main.logger.warning") as warning,
        TestClient(app),
    ):
        pass

    warning.assert_called_once_with("Database not available at startup")


def test_run_invokes_uvicorn() -> None:
    with patch("uvicorn.run") as uvicorn_run:
        main.run()

    uvicorn_run.assert_called_once()


def test_module_main_entrypoint_runs_server() -> None:
    with patch("uvicorn.run") as uvicorn_run, warnings.catch_warnings():
        # runpy warns because api.main is already imported; that is expected here.
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("api.main", run_name="__main__")

    uvicorn_run.assert_called_once()
