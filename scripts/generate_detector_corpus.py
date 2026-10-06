#!/usr/bin/env python3
"""Generate the public detector-eval corpus v1 (M26 COR-1, #323).

Renders the field-test scenarios + benign false-positive traffic into a
versioned, machine-checkable manifest. Shape-synthesized only; no copied
content. CI asserts the committed manifest is current.

Usage: python scripts/generate_detector_corpus.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "analytics" / "src"))

from analytics.scenario_validation import export_public_corpus  # noqa: E402

OUT = REPO / "schema" / "vectors" / "detectors" / "detector-corpus-v1.json"


def render() -> str:
    return json.dumps(export_public_corpus(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text = render()
    if "--check" in args:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("detector corpus v1 is stale; run scripts/generate_detector_corpus.py", file=sys.stderr)
            return 1
        print("detector corpus v1 is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
