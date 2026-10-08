#!/usr/bin/env python3
"""M31 31.2 — cross-harness test-kit replay / self-test / cross-parser (XHT).

F-3 fix: nothing registers adapters in-process, so register the **shipped**
adapters through the SDK's own conformance registry — the single source of
truth for each adapter's capabilities, documented gaps and conformance fixture
corpus — then run the contract against them.

Modes (argv):
  --self-test            every registered adapter conforms (all checks ok)
  --cross-parser         >=2 independent parsers are registered
  --opencode --bounded   (LUI-2/AGI-2 tail) bounded long-tail reader
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agentwatch  # noqa: E402
from agentwatch import conformance  # noqa: E402
from _ftutil import ok  # noqa: E402


def _register() -> None:
    """Register the shipped adapters via the SDK's canonical registry."""
    sdk_root = Path(agentwatch.__file__).resolve().parents[2]  # packages/python-sdk
    tests = sdk_root / "tests"
    if str(tests) not in sys.path:
        sys.path.insert(0, str(tests))
    import conformance_registry  # noqa: F401  (registers every shipped adapter)


def main(argv):
    _register()
    names = conformance.registered_names()
    assert names, "no adapters registered"
    results = conformance.run_registered()
    if "--self-test" in argv:
        assert results, "replay produced no results"
        assert all(r.ok for r in results), [r.summary() for r in results]
    if "--cross-parser" in argv:
        assert len(names) >= 2, "need >=2 independent parsers"
    ok(f"xht replay across {len(names)} adapters; broken adapter fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
