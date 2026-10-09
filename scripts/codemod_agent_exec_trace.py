#!/usr/bin/env python3
"""Codemod: ``agent_exec_trace`` → ``agentwatch`` (M28 GOV-1, #369; PRD 46).

The shipped package kept its legacy import path through a compatibility shim
(DD-12), but new instrumentation should use the canonical ``agentwatch``
namespace. This rewrites the *identifier* in Python source — imports, aliases,
submodule paths, and attribute references — while leaving string literals and
comments (historical mentions) untouched.

Usage::

    python scripts/codemod_agent_exec_trace.py [--check] PATH [PATH ...]
    python scripts/codemod_agent_exec_trace.py -        # stdin -> stdout

``--check`` reports files that would change and exits non-zero without writing.
"""

from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

OLD = "agent_exec_trace"
NEW = "agentwatch"


def codemod_source(source: str) -> tuple[str, int]:
    """Rewrite the legacy *identifier* in ``source``; return (new_source, count).

    A ``NAME`` token is the only thing rewritten, so string literals, comments,
    and attribute-name text in docstrings are never corrupted.
    """
    line_starts = [0]
    for line in source.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))

    replacements: list[tuple[int, int]] = []
    readline = io.StringIO(source).readline
    for token in tokenize.generate_tokens(readline):
        if token.type == tokenize.NAME and token.string == OLD:
            start = line_starts[token.start[0] - 1] + token.start[1]
            end = line_starts[token.end[0] - 1] + token.end[1]
            replacements.append((start, end))

    if not replacements:
        return source, 0
    out = source
    for start, end in reversed(replacements):
        out = out[:start] + NEW + out[end:]
    return out, len(replacements)


def _codemod_file(path: Path, *, check: bool) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    rewritten, count = codemod_source(original)
    if count == 0:
        return False
    if check:
        print(f"would rewrite {path} ({count} reference(s))", file=sys.stderr)
    else:
        path.write_text(rewritten, encoding="utf-8")
        print(f"rewrote {path} ({count} reference(s))")
    return True


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    paths = [arg for arg in args if not arg.startswith("--")]

    if paths == ["-"]:
        rewritten, _count = codemod_source(sys.stdin.read())
        sys.stdout.write(rewritten)
        return 0

    changed = False
    for target in paths:
        changed = _codemod_file(Path(target), check=check) or changed
    return 1 if (check and changed) else 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
