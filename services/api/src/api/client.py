"""Generated typed client for the agentwatch API (M26 API-1).

Do not edit by hand: run ``python scripts/generate_openapi.py``. The client is
drift-checked against the FastAPI app in CI.
"""

from __future__ import annotations

from typing import Any

import httpx


class AgentwatchClient:
    """A thin typed client over the published OpenAPI contract."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = client or httpx.Client(base_url=base_url, headers=headers)

    def get_anomalies(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/anomalies"""
        return self._client.get("/api/v1/anomalies", params=params)

    def get_attribution(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/attribution"""
        return self._client.get("/api/v1/attribution", params=params)

    def get_compare(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/compare"""
        return self._client.get("/api/v1/compare", params=params)

    def get_detector_telemetry(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/detector-telemetry"""
        return self._client.get("/api/v1/detector-telemetry", params=params)

    def get_fleet(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/fleet"""
        return self._client.get("/api/v1/fleet", params=params)

    def get_run_timeline(
        self, run_id: str, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/runs/{run_id}"""
        return self._client.get(f"/api/v1/runs/{run_id}", params=params)

    def get_siem_health(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/siem-health"""
        return self._client.get("/api/v1/siem-health", params=params)

    def health(
        self, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """GET /api/v1/health"""
        return self._client.get("/api/v1/health", params=params)

    def close(self) -> None:
        self._client.close()


__all__ = ["AgentwatchClient"]
