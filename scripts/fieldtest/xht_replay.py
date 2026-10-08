#!/usr/bin/env python3
"""M31 31.2 — cross-harness test-kit replay / self-test / cross-parser (XHT).

F-3 fix: nothing registers adapters in-process, so register the shipped
harness adapters (with their real capability/gap declarations and fixture
corpora) and run the contract against them.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import conformance  # real API
from agentwatch.adapters import codex_cli, cursor, gemini_cli
from _ftutil import ok

FIXTURES = Path("/ft/fixtures")

# (name, module, error class, fixtures dir)
SHIPPED = [
    ("cursor", cursor, cursor.CursorAdapterError, FIXTURES / "cursor"),
    ("codex", codex_cli, codex_cli.CodexCliAdapterError, FIXTURES / "codex"),
    ("gemini", gemini_cli, gemini_cli.GeminiCliAdapterError, FIXTURES / "gemini"),
]


def _register() -> None:
    for name, mod, error_cls, fixtures_dir in SHIPPED:
        conformance.register(
            conformance.AdapterSpec(
                name=name,
                normalize=mod.normalize,
                capabilities=mod.CAPABILITIES,
                documented_gaps=mod.DOCUMENTED_GAPS,
                error_cls=error_cls,
                fixtures_dir=fixtures_dir,
            ),
            replace=True,
        )


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
