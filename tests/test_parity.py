"""Full-parity gate (M13 13.7, PRD 10 A1–A6).

Runs the release parity check so the shipped-feature superset cannot silently
regress. See ``scripts/check_parity.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_full_parity_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_parity.py")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "all A1–A6 rows delivered" in result.stdout
