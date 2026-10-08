#!/usr/bin/env python3
"""M31 31.2 — ingest recorded fixtures for a harness/surface kind."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, fixture, ok, records, run


def main(argv: list[str]) -> int:
    kind = arg(argv, "--kind", "generic")
    corpus = arg(argv, "--corpus")
    path = Path(corpus) if corpus else fixture(kind)
    run(["agentwatch", "ingest", "--format", kind, str(path)])
    run(["agentwatch", "verify-store"])
    ok(f"ingested {kind} from {path} ({len(records())} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
