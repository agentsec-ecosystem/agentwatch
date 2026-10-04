#!/usr/bin/env python3
"""Write SHA-256 checksums for built artifacts (M13 13.5)."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checksums")
    parser.add_argument("--dist", default=str(REPO / "dist"))
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    dist = Path(args.dist)
    artifacts = sorted(p for p in dist.glob("*") if p.is_file() and p.name != "SHA256SUMS")
    output = Path(args.output) if args.output else dist / "SHA256SUMS"
    lines = [f"{checksum(path)}  {path.name}" for path in artifacts]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"checksums: wrote {output} ({len(artifacts)} artifact(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
