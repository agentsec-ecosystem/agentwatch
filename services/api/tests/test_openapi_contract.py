"""OpenAPI publication + typed-client drift contract (M26 API-1, #330).

The FastAPI app is the single source of truth. ``openapi.json`` and the typed
client are generated from it; this test regenerates both and fails on drift, and
asserts the client exposes exactly one method per OpenAPI operation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]
OPENAPI = REPO / "services" / "api" / "openapi.json"
CLIENT = REPO / "services" / "api" / "src" / "api" / "client.py"


def _load_generator() -> ModuleType:
    path = REPO / "scripts" / "generate_openapi.py"
    sys.path.insert(0, str(REPO / "services" / "api" / "src"))
    spec = importlib.util.spec_from_file_location("generate_openapi", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = _load_generator()


def test_published_openapi_matches_the_app() -> None:
    assert OPENAPI.read_text(encoding="utf-8") == generator.render_openapi()


def test_typed_client_matches_the_generator() -> None:
    assert CLIENT.read_text(encoding="utf-8") == generator.render_client()


def test_client_has_one_method_per_operation() -> None:
    from api.client import AgentwatchClient

    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    operation_ids = {
        op["operationId"]
        for ops in spec["paths"].values()
        for op in ops.values()
        if "operationId" in op
    }

    assert operation_ids
    for operation_id in operation_ids:
        assert callable(getattr(AgentwatchClient, operation_id, None)), operation_id


def test_openapi_paths_are_the_v1_contract() -> None:
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))

    assert set(spec["paths"]) >= {
        "/api/v1/health",
        "/api/v1/runs/{run_id}",
        "/api/v1/fleet",
        "/api/v1/compare",
        "/api/v1/anomalies",
    }
