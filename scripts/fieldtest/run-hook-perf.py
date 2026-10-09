#!/usr/bin/env python3
"""DEP-3: end-to-end hook wall-clock gate (p99 <= 250 ms) + a 500-call quote."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    "/work/packages/python-sdk/src",
    os.path.join(_HERE, "..", "..", "packages", "python-sdk", "src"),
):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)

from agentwatch import hook_perf  # noqa: E402


def main() -> int:
    wc = hook_perf.measure_hook_wallclock(iterations=25)
    if wc.blocked:
        print(f"blocked ({wc.os_name}): {wc.block_reason}", file=sys.stderr)
        return 1
    print(f"hook wall-clock: p50={wc.stats.p50_ms:.2f}ms p99={wc.stats.p99_ms:.2f}ms "
          f"max={wc.stats.max_ms:.2f}ms budget={wc.budget_ms:.0f}ms")
    print(f"500-call session overhead at p99: {wc.session_overhead_ms(500):.1f} ms")
    if not wc.within_budget:
        print(f"FAIL: hook p99 {wc.stats.p99_ms:.2f} ms > budget {wc.budget_ms:.1f} ms",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
