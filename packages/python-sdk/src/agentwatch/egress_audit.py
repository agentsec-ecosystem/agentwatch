"""Dependency egress audit (M12 K2, PRD 28).

R6/NFR-9 is a guarantee: no egress by default. This static audit fails when the
SDK source imports a known egress-capable library that is not explicitly allowed,
so a stray phone-home is caught in CI before it ships.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Libraries whose presence implies the ability to talk to the network.
EGRESS_LIBS = frozenset(
    {
        "requests",
        "httpx",
        "urllib3",
        "aiohttp",
        "websockets",
        "websocket",
        "grpc",
        "httplib2",
        "socketio",
        "boto3",
        "botocore",
        "paramiko",
        "smtplib",
        "ftplib",
        "telnetlib",
    }
)


def _import_roots(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def stdlib_modules() -> frozenset[str]:
    return frozenset(getattr(sys, "stdlib_module_names", frozenset()))


def audit(
    source_dir: Path | str,
    *,
    allowed: frozenset[str] = frozenset({"opentelemetry", "agentwatch"}),
    banned: frozenset[str] = EGRESS_LIBS,
) -> list[str]:
    """Return findings for egress-capable imports in ``source_dir`` (empty = clean)."""
    findings: list[str] = []
    for path in sorted(Path(source_dir).rglob("*.py")):
        for root in sorted(_import_roots(path)):
            if root in banned and root not in allowed:
                findings.append(f"{path}: egress-capable import {root!r}")
    return findings


def third_party_roots(source_dir: Path | str) -> set[str]:
    """First-party module roots imported anywhere under ``source_dir``."""
    stdlib = stdlib_modules()
    roots: set[str] = set()
    for path in sorted(Path(source_dir).rglob("*.py")):
        for root in _import_roots(path):
            if root not in stdlib and root != "agentwatch":
                roots.add(root)
    return roots
