#!/usr/bin/env python3
"""Build the standalone ``agentwatch-verify`` zipapp (M15 S12, #232).

Packages ``scripts/agentwatch_verify/`` (stdlib only) into a single executable
``.pyz`` an auditor can run on any machine with Python, no install.
"""

from __future__ import annotations

import argparse
import zipapp
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "scripts" / "agentwatch_verify"


def build(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(
        SOURCE,
        target=output,
        interpreter="/usr/bin/env python3",
        compressed=True,
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_verify_zipapp")
    parser.add_argument("--output", default=str(REPO / "dist" / "agentwatch-verify.pyz"))
    args = parser.parse_args(argv)
    output = build(Path(args.output))
    print(f"agentwatch-verify: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
