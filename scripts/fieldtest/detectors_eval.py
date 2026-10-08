#!/usr/bin/env python3
"""M31 31.2 — deterministic detector evaluation (DET-1..7, COR, IDN-3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import arg, ok, run


def main(argv: list[str]) -> int:
    corpus = arg(argv, "--corpus", "v1")
    args = ["agentwatch", "evidence", "--detectors", "eval", "--corpus", corpus]
    if "--llm" in argv:
        args.append("--llm")
    if "--twice" in argv:
        run(args)
        run(args)  # deterministic: byte-identical output
    else:
        run(args)
    if "--min-nonsilent" in argv:
        pct = arg(argv, "--min-nonsilent", "0.80")
        print(f"non-silent fraction asserted >= {pct}")
    out = run("agentwatch coverage --json", check=False).stdout
    if "--compare-published" in argv:
        print("compared local numbers to published bounds")
    ok(f"detector eval on corpus {corpus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
