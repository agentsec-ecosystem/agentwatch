#!/usr/bin/env python3
"""Claims-ledger check (PRD 38 §Q9, issue #226).

Every public claim must trace to **live** evidence. The ledger
(``docs/release/claims-ledger.json``) is the source of truth; the table in
``docs/release/claims-ledger.md`` is generated from it. This check fails when a
claim has no evidence, when an evidence link is broken (a renamed test, a deleted
file), or when the published table has drifted from the ledger.

Evidence reference syntax::

    test:<repo-relative path>::<function>   a pytest test that must still exist (checked via AST)
    file:<path>                             a committed file
    script:<path>                           a committed script
    workflow:<path>                         a committed workflow
    doc:<path>                              a committed doc

Usage::

    python scripts/check_claims.py            # check the ledger (CI)
    python scripts/check_claims.py --self-test  # prove broken claims fail the check
    python scripts/check_claims.py --write      # regenerate the published table
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEDGER_JSON = REPO / "docs" / "release" / "claims-ledger.json"
LEDGER_MD = REPO / "docs" / "release" / "claims-ledger.md"
BEGIN = "<!-- BEGIN GENERATED: claims -->"
END = "<!-- END GENERATED: claims -->"
_FILE_TYPES = {"file", "script", "workflow", "doc"}


def load_ledger(path: Path = LEDGER_JSON) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def resolve_evidence(ref: str, repo: Path = REPO) -> str | None:
    """Return an error string when ``ref`` does not resolve, else ``None``."""
    kind, sep, target = ref.partition(":")
    if not sep or not target:
        return f"malformed evidence ref {ref!r}"
    if kind == "test":
        path_str, sep2, func = target.partition("::")
        if not sep2 or not func:
            return f"test ref needs <path>::<function>: {ref!r}"
        path = repo / path_str
        if not path.is_file():
            return f"test file missing: {path_str}"
        if func not in _defined_functions(path):
            return f"test {func} not found in {path_str}"
        return None
    if kind in _FILE_TYPES:
        if not (repo / target).is_file():
            return f"{kind} missing: {target}"
        return None
    return f"unknown evidence type {kind!r} in {ref!r}"


def validate(ledger: dict[str, Any], repo: Path = REPO) -> list[str]:
    """Return every problem with the ledger (empty means it passes)."""
    errors: list[str] = []
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["ledger must have a non-empty 'claims' list"]
    today = date.today()
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claim #{index} is not an object")
            continue
        cid = str(claim.get("id", f"#{index}"))
        for field in ("id", "claim", "source", "evidence", "last_verified"):
            if not claim.get(field):
                errors.append(f"{cid}: missing {field}")
        if cid in seen:
            errors.append(f"{cid}: duplicate id")
        seen.add(cid)

        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{cid}: no evidence link (add evidence or remove the claim)")
        else:
            for ref in evidence:
                problem = resolve_evidence(str(ref), repo)
                if problem:
                    errors.append(f"{cid}: {problem}")

        verified = claim.get("last_verified")
        if verified:
            try:
                when = date.fromisoformat(str(verified))
            except ValueError:
                errors.append(f"{cid}: last_verified is not an ISO date: {verified!r}")
            else:
                if when > today:
                    errors.append(f"{cid}: last_verified is in the future: {verified}")
    return errors


def render_table(ledger: dict[str, Any]) -> str:
    rows = ["| ID | Claim | Source | Evidence | Last verified |", "|---|---|---|---|---|"]
    for claim in ledger["claims"]:
        evidence = "<br>".join(f"`{ref}`" for ref in claim["evidence"])
        rows.append(
            f"| `{claim['id']}` | {claim['claim']} | `{claim['source']}` | {evidence} | "
            f"{claim['last_verified']} |"
        )
    return "\n".join(rows)


def extract_block(markdown: str) -> str:
    _, _, rest = markdown.partition(BEGIN)
    block, _, _ = rest.partition(END)
    return block.strip()


def run(repo: Path = REPO) -> list[str]:
    ledger = load_ledger(repo / "docs" / "release" / "claims-ledger.json")
    errors = validate(ledger, repo)
    markdown = (repo / "docs" / "release" / "claims-ledger.md").read_text(encoding="utf-8")
    if extract_block(markdown) != render_table(ledger).strip():
        errors.append(
            "docs/release/claims-ledger.md is out of date; re-run scripts/check_claims.py --write"
        )
    return errors


def self_test(repo: Path = REPO) -> list[str]:
    """Prove the check fails on an evidence-less, renamed, or unknown link."""
    problems: list[str] = []
    base = {"claim": "x", "source": "s", "last_verified": "2026-01-01"}
    no_evidence = {"claims": [{**base, "id": "X", "evidence": []}]}
    if not any("no evidence" in error for error in validate(no_evidence, repo)):
        problems.append("a claim with no evidence did not fail")
    renamed = {
        "claims": [
            {
                **base,
                "id": "X",
                "evidence": [
                    "test:packages/python-sdk/tests/test_replay.py::test_this_was_renamed"
                ],
            }
        ]
    }
    if not any("not found" in error for error in validate(renamed, repo)):
        problems.append("a renamed test link did not fail")
    unknown = {"claims": [{**base, "id": "X", "evidence": ["nope:whatever"]}]}
    if not any("unknown evidence type" in error for error in validate(unknown, repo)):
        problems.append("an unknown evidence type did not fail")
    return problems


def _write(repo: Path = REPO) -> int:
    ledger = load_ledger(repo / "docs" / "release" / "claims-ledger.json")
    path = repo / "docs" / "release" / "claims-ledger.md"
    markdown = path.read_text(encoding="utf-8")
    pre, sep, rest = markdown.partition(BEGIN)
    _, sep2, post = rest.partition(END)
    if not sep or not sep2:
        print("generated-table markers missing from claims-ledger.md", file=sys.stderr)
        return 1
    path.write_text(pre + BEGIN + "\n" + render_table(ledger) + "\n" + END + post, encoding="utf-8")
    print(f"updated {path.relative_to(repo)}")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        problems = self_test()
        if problems:
            print("claims self-test FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("claims self-test OK: evidence-less, renamed, and unknown links all fail")
        return 0
    if "--write" in argv:
        return _write()
    errors = run()
    if errors:
        print("claims ledger FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    ledger = load_ledger()
    links = sum(len(claim["evidence"]) for claim in ledger["claims"])
    print(f"claims ledger OK: {len(ledger['claims'])} claims, {links} live evidence links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
