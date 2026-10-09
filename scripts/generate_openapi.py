#!/usr/bin/env python3
"""Generate the published OpenAPI document and the typed Python client (M26 API-1).

The FastAPI app is the single source of truth: this script renders
``services/api/openapi.json`` and ``services/api/src/api/client.py`` from it.
CI asserts both committed artifacts match the app, so the published contract and
the client cannot drift.

Usage: python scripts/generate_openapi.py [--check]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
API_SRC = REPO / "services" / "api" / "src"
OPENAPI_OUT = REPO / "services" / "api" / "openapi.json"
CLIENT_OUT = API_SRC / "api" / "client.py"

sys.path.insert(0, str(API_SRC))

from api.main import app  # noqa: E402

_PARAM = re.compile(r"\{([^}]+)\}")
_HEADER = (
    '"""Generated typed client for the agentwatch API (M26 API-1).\n\n'
    "Do not edit by hand: run ``python scripts/generate_openapi.py``. The client is\n"
    "drift-checked against the FastAPI app in CI.\n\"\"\"\n\n"
    "from __future__ import annotations\n\n"
    "from typing import Any\n\n"
    "import httpx\n\n\n"
)


def render_openapi() -> str:
    """The published OpenAPI document, deterministically rendered."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def _operations() -> list[tuple[str, str, str, list[str]]]:
    """(operationId, method, path, path-params) sorted by operationId."""
    spec = app.openapi()
    operations: list[tuple[str, str, str, list[str]]] = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            operation_id = str(op.get("operationId") or f"{method}_{path}")
            params = _PARAM.findall(path)
            operations.append((operation_id, method.lower(), path, params))
    return sorted(operations)


def _render_method(operation_id: str, method: str, path: str, params: list[str]) -> str:
    args = "".join(f"{name}: str, " for name in params)
    target = f'f"{path}"' if params else f'"{path}"'
    return (
        f"    def {operation_id}(\n"
        f"        self, {args}*, params: dict[str, Any] | None = None\n"
        f"    ) -> httpx.Response:\n"
        f'        """{method.upper()} {path}"""\n'
        f"        return self._client.{method}({target}, params=params)\n\n"
    )


def render_client() -> str:
    """The typed client source, one method per OpenAPI operation."""
    methods = "".join(
        _render_method(operation_id, method, path, params)
        for operation_id, method, path, params in _operations()
    )
    body = (
        "class AgentwatchClient:\n"
        '    """A thin typed client over the published OpenAPI contract."""\n\n'
        "    def __init__(\n"
        "        self,\n"
        "        base_url: str,\n"
        "        *,\n"
        "        client: httpx.Client | None = None,\n"
        "        headers: dict[str, str] | None = None,\n"
        "    ) -> None:\n"
        "        self._client = client or httpx.Client(base_url=base_url, headers=headers)\n\n"
        f"{methods}"
        "    def close(self) -> None:\n"
        "        self._client.close()\n\n"
        '\n__all__ = ["AgentwatchClient"]\n'
    )
    return _HEADER + body


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    artifacts = {OPENAPI_OUT: render_openapi(), CLIENT_OUT: render_client()}
    if check:
        stale = [path for path, text in artifacts.items() if path.read_text(encoding="utf-8") != text]
        if stale:
            names = ", ".join(str(p.relative_to(REPO)) for p in stale)
            print(f"OpenAPI artifacts are stale: {names}; run scripts/generate_openapi.py", file=sys.stderr)
            return 1
        print("OpenAPI artifacts are current")
        return 0
    for path, text in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
