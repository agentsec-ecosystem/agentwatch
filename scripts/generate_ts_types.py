#!/usr/bin/env python3
"""Generate TypeScript types from a JSON Schema (M28 TSS-1 spike, #368; PRD 46).

This is a **spike**, not a shipped generator: it proves the JSON Schema in
`schema/` is portable to generated TypeScript, so the v0.3.0 TypeScript-SDK
decision (ADR-0049) rests on evidence rather than optimism. It handles the shapes
the record/security-event schemas use — objects, enums, arrays, primitives, and
`["type", "null"]` unions.

Usage::

    python scripts/generate_ts_types.py [SCHEMA] [--out FILE]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPO / "schema" / "agent-record.schema.json"

_HEADER = (
    "// AUTO-GENERATED from a schema/ JSON Schema by scripts/generate_ts_types.py\n"
    "// Do not edit by hand (spike; TSS-1).\n"
)


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^0-9a-zA-Z]+", name) if part)


class _Generator:
    def __init__(self) -> None:
        self._interfaces: list[str] = []
        self._emitted: set[str] = set()

    def _type(self, prop: dict[str, Any], hint: str) -> str:
        if "enum" in prop:
            return " | ".join(json.dumps(value) for value in prop["enum"])
        declared = prop.get("type")
        if isinstance(declared, list):
            return " | ".join(self._type({**prop, "type": item}, hint) for item in declared)
        if declared == "object" or "properties" in prop:
            self._interface(hint, prop)
            return hint
        if declared == "array":
            return f"{self._type(prop.get('items', {}), hint + 'Item')}[]"
        if declared in {"integer", "number"}:
            return "number"
        if declared == "boolean":
            return "boolean"
        if declared == "null":
            return "null"
        if declared == "string":
            return "string"
        return "unknown"

    def _interface(self, name: str, schema: dict[str, Any]) -> None:
        if name in self._emitted:
            return
        self._emitted.add(name)
        required = set(schema.get("required", []))
        body: list[str] = []
        for key, prop in schema.get("properties", {}).items():
            optional = "" if key in required else "?"
            body.append(f"  {key}{optional}: {self._type(prop, name + _pascal(key))};")
        self._interfaces.append(f"export interface {name} {{\n" + "\n".join(body) + "\n}")

    def render(self, schema: dict[str, Any], root_name: str) -> str:
        self._interface(root_name, schema)
        return _HEADER + "\n" + "\n\n".join(self._interfaces) + "\n"


def generate_typescript(schema: dict[str, Any], *, root_name: str = "AgentRecord") -> str:
    """Generate TypeScript interfaces for a JSON Schema."""
    return _Generator().render(schema, root_name)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    out: Path | None = None
    if "--out" in args:
        index = args.index("--out")
        out = Path(args[index + 1])
        del args[index : index + 2]
    schema_path = Path(args[0]) if args else DEFAULT_SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    text = generate_typescript(schema)
    if out is not None:
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
