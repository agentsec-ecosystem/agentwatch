#!/usr/bin/env python3
"""Executable documentation (PRD 38 §Q10, issue #227).

Docs that cannot execute are a build failure, not a stale page. This checker
extracts the fenced blocks a doc explicitly opts into and runs them against the
synthetic seed dataset (``scripts/seed-investigations.py``), offline.

Fence annotation (the info string):

    ```sh run       execute this block in CI
    ```sh service   needs the compose stack; covered by Q5 (skipped here)
    ```sh           illustrative; not executed

Scope: the J3 investigation cookbook (``docs/examples/investigations/``). The
tutorials are install/network/service or code-writing guides; their commands are
not deterministic offline, so they are covered by link-checking and the
compose-backed job rather than here.

Usage::

    python scripts/check_docs_commands.py            # run every `run` block
    python scripts/check_docs_commands.py --list     # list the extracted commands
    python scripts/check_docs_commands.py --self-test  # prove a broken command fails
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC_GLOBS = ("docs/examples/investigations/*.md",)
_FENCE = re.compile(r"^```(?P<info>[^\n`]*)\n(?P<body>.*?)^```[ \t]*$", re.M | re.DOTALL)


@dataclass(frozen=True)
class Block:
    """A fenced code block and the mode its info string declares."""

    path: Path
    lang: str
    mode: str
    line: int
    script: str


def _join_commands(body: str) -> str:
    lines: list[str] = []
    pending = ""
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line + "\n"
            continue
        lines.append(pending + line)
        pending = ""
    if pending:
        lines.append(pending)
    return "\n".join(lines)


def extract_blocks(markdown: str, path: Path) -> list[Block]:
    """Return every annotated (``run``/``service``) fenced block in ``markdown``."""
    blocks: list[Block] = []
    for match in _FENCE.finditer(markdown):
        tokens = match.group("info").split()
        if not tokens:
            continue
        mode = "run" if "run" in tokens else "service" if "service" in tokens else ""
        if not mode:
            continue
        body = match.group("body")
        if not body.strip():
            continue
        line = markdown[: match.start()].count("\n") + 1
        blocks.append(
            Block(
                path=path,
                lang=tokens[0],
                mode=mode,
                line=line,
                script=_join_commands(body),
            )
        )
    return blocks


def iter_documents(repo: Path = REPO) -> Iterable[Path]:
    for pattern in DOC_GLOBS:
        yield from sorted(repo.glob(pattern))


def _rewrite(script: str) -> str:
    """Run `agentwatch`/`python` through the current interpreter (no console script needed)."""
    python = shlex.quote(sys.executable)
    script = re.sub(r"(?m)^(\s*)agentwatch\b", rf"\1{python} -m agentwatch", script)
    script = re.sub(r"(?m)^(\s*)python3?\b", rf"\1{python}", script)
    return script


def _environment(home: Path, store: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AGENTWATCH_")}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["DEMO_STORE"] = str(store)
    pythonpath = str(REPO / "packages" / "python-sdk" / "src")
    env["PYTHONPATH"] = pythonpath + os.pathsep + env.get("PYTHONPATH", "")
    return env


def run_document(path: Path, repo: Path = REPO, tmp: Path | None = None) -> list[str]:
    """Execute every `run` block in one document against a fresh seeded store."""
    errors: list[str] = []
    all_blocks = extract_blocks(path.read_text(encoding="utf-8"), path)
    blocks = [block for block in all_blocks if block.mode == "run"]
    if not blocks:
        return errors
    base = tmp or Path(tempfile.mkdtemp(prefix="agentwatch-docs-"))
    home = base / path.stem
    store = home / "store"
    store.mkdir(parents=True, exist_ok=True)
    env = _environment(home, store)
    try:
        label = path.relative_to(repo)
    except ValueError:
        label = path
    for block in blocks:
        result = subprocess.run(
            _rewrite(block.script),
            shell=True,
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(
                f"{label}:{block.line}: command failed "
                f"(exit {result.returncode})\n    {block.script}\n    {result.stderr.strip()}"
            )
    return errors


def check(repo: Path = REPO) -> list[str]:
    errors: list[str] = []
    for path in iter_documents(repo):
        errors.extend(run_document(path, repo))
    return errors


def _self_test(repo: Path = REPO) -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agentwatch-docs-selftest-") as raw:
        tmp = Path(raw)
        good = tmp / "good.md"
        good.write_text("# good\n\n```sh run\ntrue\n```\n", encoding="utf-8")
        if run_document(good, repo, tmp / "g"):
            problems.append("a passing command was reported as failing")
        bad = tmp / "bad.md"
        bad.write_text("# bad\n\n```sh run\nexit 7\n```\n", encoding="utf-8")
        if not run_document(bad, repo, tmp / "b"):
            problems.append("a failing command was not reported")
        skipped = tmp / "skipped.md"
        skipped.write_text(
            "# skipped\n\n```sh\nfalse\n```\n\n```sh service\nfalse\n```\n", encoding="utf-8"
        )
        if run_document(skipped, repo, tmp / "s"):
            problems.append("an illustrative/service block was executed")
    return problems


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for path in iter_documents():
            for block in extract_blocks(path.read_text(encoding="utf-8"), path):
                first = block.script.splitlines()[0]
                print(f"{path.relative_to(REPO)}:{block.line} [{block.mode}] {first}")
        return 0
    if "--self-test" in argv:
        problems = _self_test()
        if problems:
            print("docs self-test FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("docs self-test OK: passing blocks pass; failing blocks and skipped blocks behave")
        return 0
    errors = check()
    if errors:
        print("executable docs FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    count = sum(
        len([b for b in extract_blocks(path.read_text(encoding="utf-8"), path) if b.mode == "run"])
        for path in iter_documents()
    )
    print(f"executable docs OK: {count} run blocks across {len(list(iter_documents()))} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
