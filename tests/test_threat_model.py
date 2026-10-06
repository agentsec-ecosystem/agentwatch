"""Threat-model + ADR guard (M26 RSK-2, #332).

Every v0.2.0 threat-model addition row must cite a **real** regression test, and
the v0.2.0 ADR series (0016–0026) must exist with a recorded status.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THREAT = REPO / "docs" / "design" / "threat-model.md"
ADR_DIR = REPO / "docs" / "adr"

REF = re.compile(r"test:([^`\s)]+)::([A-Za-z0-9_]+)")


def _v02_section() -> str:
    text = THREAT.read_text(encoding="utf-8")
    start = text.index("## v0.2.0 additions")
    rest = text[start:]
    for marker in ("\n### ", "\n## "):
        cut = rest.find(marker, 1)
        if cut != -1:
            rest = rest[:cut]
    return rest


def _v02_rows() -> list[str]:
    rows = [
        line
        for line in _v02_section().splitlines()
        if line.strip().startswith("|")
    ]
    # Drop the header row and the |---|---| separator.
    return [row for row in rows if "---" not in row and "Scenario" not in row]


def _test_exists(path: str, func: str) -> bool:
    target = REPO / path
    if not target.is_file():
        return False
    tree = ast.parse(target.read_text(encoding="utf-8"))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func
        for node in ast.walk(tree)
    )


def test_v02_threat_rows_cite_a_real_test() -> None:
    rows = _v02_rows()
    assert len(rows) == 5, f"expected 5 v0.2.0 additions, found {len(rows)}"
    for row in rows:
        refs = REF.findall(row)
        assert refs, f"threat-model row cites no test: {row[:80]}"
        for path, func in refs:
            assert _test_exists(path, func), f"missing test {path}::{func}"


def test_v02_adr_series_exists_with_a_status() -> None:
    for number in range(16, 27):
        matches = sorted(ADR_DIR.glob(f"{number:04d}-*.md"))
        assert matches, f"ADR-{number:04d} is missing"
        text = matches[0].read_text(encoding="utf-8")
        assert "**Status:**" in text, f"ADR-{number:04d} has no status line"


TRACE = REPO / "docs" / "design" / "threat-test-traceability.md"
ATTACK = REPO / "docs" / "design" / "recorder-attack-matrix.md"

_V02_SURFACES = (
    "Streaming side-channel",
    "Proxy-surface growth",
    "Compliance-API pull",
    "Identity-field abuse",
    "Foreign-data weaponization",
)


def test_traceability_test_refs_resolve() -> None:
    refs = REF.findall(TRACE.read_text(encoding="utf-8"))
    assert refs, "traceability doc cites no test: references"
    for path, func in refs:
        assert _test_exists(path, func), f"missing test {path}::{func}"


def test_traceability_covers_every_v02_surface_with_a_test() -> None:
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    for surface in _V02_SURFACES:
        rows = [line for line in lines if surface in line]
        assert rows, f"traceability is missing the {surface} row"
        assert REF.findall(rows[0]), f"{surface} row cites no test"


def test_attack_matrix_rows_state_a_command_or_compensating_control() -> None:
    rows = [
        line
        for line in ATTACK.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("| **")
    ]
    assert rows
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        # Scenario | Preventable | Detectable | Command/evidence | Compensating
        assert len(cells) >= 5, row
        assert cells[3] or cells[4], f"row states neither evidence nor a control: {row[:80]}"
