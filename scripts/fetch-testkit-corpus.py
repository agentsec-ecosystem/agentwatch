#!/usr/bin/env python3
"""Re-fetch the cross-harness test-kit corpus from pinned upstream commits.

This is the reproducibility record for ``packages/python-sdk/tests/testkit``:
each corpus is cloned from a pinned commit and copied into place, and a
``checksums.json`` lock is (re)written so the staged bytes can be verified
offline. The corpus is licensed third-party test data (MIT); upstream LICENSE
files are copied beside each corpus and attributed in ``THIRD_PARTY_NOTICES.md``.

Offline (no network) usage::

    python3 scripts/fetch-testkit-corpus.py --check     # verify staged vs lock
    python3 scripts/fetch-testkit-corpus.py --rehash    # rewrite the lock only

Network usage (maintenance, e.g. to add a corpus)::

    python3 scripts/fetch-testkit-corpus.py             # fetch + restage + lock

The Cursor **vendor** payload corpus (``cursor/vendor-1.7.2``) is not fetched:
its payloads are transcribed from the published Cursor hooks reference
(https://cursor.com/docs/hooks, retrieved 2026-10-05) into the conformance pack
``tests/fixtures/cursor/*.json`` and reviewed by hand — see PROVENANCE.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KIT = REPO / "packages" / "python-sdk" / "tests" / "testkit"
LOCK = KIT / "checksums.json"


@dataclass(frozen=True)
class Corpus:
    """One upstream corpus: pinned repo + paths copied into the kit."""

    harness: str
    directory: str
    repo: str
    commit: str
    license: str
    copies: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    # (upstream path/glob, destination subdir, glob)


CORPORA: tuple[Corpus, ...] = (
    Corpus(
        harness="claude-code",
        directory="claude-code/ouija",
        repo="https://github.com/kylesnowschwartz/agent-ouija",
        commit="c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc",
        license="LICENSE",
        copies=(("claude/testdata", "rollouts", "*.jsonl"),),
    ),
    Corpus(
        harness="codex",
        directory="codex/ouija",
        repo="https://github.com/kylesnowschwartz/agent-ouija",
        commit="c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc",
        license="LICENSE",
        copies=(("codex/rollout/testdata", "rollouts", "*.jsonl"),),
    ),
    Corpus(
        harness="cursor",
        directory="cursor/cursor-session-tracer",
        repo="https://github.com/indranildchandra/cursor-session-tracer",
        commit="78219cea67e92d03bc9b5d96798adfac0636cbc9",
        license="LICENSE",
        copies=((".cursor/traces", "traces", "*.json"),),
    ),
)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def fetch(corpus: Corpus, workdir: Path) -> Path:
    """Clone ``corpus.repo`` at its pinned commit and return the checkout root."""
    dest = workdir / corpus.directory.replace("/", "__")
    dest.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=dest)
    _git("remote", "add", "origin", corpus.repo, cwd=dest)
    _git("fetch", "-q", "--depth", "1", "origin", corpus.commit, cwd=dest)
    _git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    return dest


def restage(corpus: Corpus, checkout: Path) -> None:
    target = KIT / corpus.directory
    for subdir in {item[1] for item in corpus.copies}:
        shutil.rmtree(target / subdir, ignore_errors=True)
    (target / corpus.license).write_bytes((checkout / corpus.license).read_bytes())
    for source, subdir, pattern in corpus.copies:
        out = target / subdir
        out.mkdir(parents=True, exist_ok=True)
        for path in sorted((checkout / source).glob(pattern)):
            shutil.copy2(path, out / path.name)


def build_lock() -> dict[str, object]:
    files: dict[str, object] = {}
    for path in sorted(KIT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(KIT).as_posix()
        if rel in {"checksums.json", "PROVENANCE.md", "README.md"} or path.name == "manifest.json":
            continue
        data = path.read_bytes()
        files[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    corpora = [
        {
            "harness": c.harness,
            "directory": c.directory,
            "repo": c.repo,
            "commit": c.commit,
        }
        for c in CORPORA
    ]
    return {"version": 1, "corpora": corpora, "files": files}


def write_lock() -> None:
    LOCK.write_text(json.dumps(build_lock(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check() -> int:
    if not LOCK.exists():
        print("no checksums.json lock", file=sys.stderr)
        return 1
    locked = json.loads(LOCK.read_text(encoding="utf-8")).get("files", {})
    actual = build_lock()["files"]
    problems: list[str] = []
    for rel in sorted(set(locked) | set(actual)):
        if rel not in actual:
            problems.append(f"missing: {rel}")
        elif rel not in locked:
            problems.append(f"untracked: {rel}")
        elif locked[rel]["sha256"] != actual[rel]["sha256"]:
            problems.append(f"changed: {rel}")
    if problems:
        print("testkit corpus drift:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"testkit corpus verified ({len(actual)} files)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify staged files against the lock")
    parser.add_argument("--rehash", action="store_true", help="rewrite the lock from staged files")
    args = parser.parse_args(argv)

    if args.check:
        return check()
    if args.rehash:
        write_lock()
        print(f"wrote {LOCK.relative_to(REPO)}")
        return 0

    with tempfile.TemporaryDirectory(prefix="agentwatch-testkit-") as tmp:
        workdir = Path(tmp)
        for corpus in CORPORA:
            checkout = fetch(corpus, workdir)
            restage(corpus, checkout)
            print(f"staged {corpus.directory} @ {corpus.commit[:12]}")
    write_lock()
    print(f"wrote {LOCK.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
