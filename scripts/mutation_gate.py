#!/usr/bin/env python3
"""Deterministic mutation gate for the trust path (PRD 38 §Q2, issue #219).

Coverage says lines ran; it does not say the assertions would catch a defect. This
gate mutates the three trust-critical surfaces — the chain/store verifier,
redaction, and ``validate_record``/``validate_event`` — and fails if any mutant
*survives* the focused test suite. A survivor means the tests would pass while the
trust guarantee is broken.

Design note: this is deliberately a small, curated, deterministic set of semantic
mutations rather than a full off-the-shelf run. ``cosmic-ray`` was evaluated (see
``docs/reference/tech-stack.md``) but its filter/DB layer is unstable on the
supported Python, and a whole-repo tool run is minutes-per-module — too slow and
too brittle to gate every change on. The curated set covers the highest-value
guarantees, runs in seconds, and is fully reproducible. Deep tool runs remain a
manual, non-gating activity; the enforced CI check is this gate.

Usage:
    python scripts/mutation_gate.py [--budget N] [--only ID ...] [--self-test]

Exit codes:
    0  survivors (outside the allow-list) <= budget
    1  survivors exceed the budget, or a mutation anchor is missing/ambiguous
    2  usage error
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "packages" / "python-sdk"
SRC = PKG / "src"


@dataclass(frozen=True)
class Mutation:
    """One semantic mutation of a trust-path source line."""

    id: str
    module: str  # path relative to SRC
    old: str
    new: str
    tests: tuple[str, ...]  # test paths relative to PKG
    rationale: str


@dataclass(frozen=True)
class MutationResult:
    id: str
    survived: bool
    returncode: int


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        id="store.chain-seq-and-prev-hash",
        module="agentwatch/store.py",
        old="if entry.seq != expected_seq or entry.prev_hash != prev:",
        new="if False:  # MUTANT",
        tests=("tests/test_store.py", "tests/test_store_hardening.py"),
        rationale="Disabling the seq/prev-hash link check must break chain verification.",
    ),
    Mutation(
        id="store.chain-checkpoint-hash",
        module="agentwatch/store.py",
        old="if _entry_hash(entry.prev_hash, payload) != entry.hash:",
        new="if False:  # MUTANT",
        tests=("tests/test_store_hardening.py", "tests/test_purge.py"),
        rationale="Disabling the checkpoint hash check must let a tampered checkpoint verify.",
    ),
    Mutation(
        id="store.chain-record-hash",
        module="agentwatch/store.py",
        old="and _entry_hash(entry.prev_hash, entry.record.to_dict()) != entry.hash",
        new="and False  # MUTANT",
        tests=("tests/test_store.py", "tests/test_store_hardening.py"),
        rationale="Disabling the record hash check must let an edited record verify.",
    ),
    Mutation(
        id="redact.field-and-mode-gate",
        module="agentwatch/redact.py",
        old="if not allowed or self.mode is PrivacyMode.METADATA_ONLY:",
        new="if False:  # MUTANT",
        tests=("tests/test_redact.py",),
        rationale="Dropping the double gate must leak a disallowed/metadata-only field.",
    ),
    Mutation(
        id="redact.truncate-boundary",
        module="agentwatch/redact.py",
        old="if len(value) > self.truncate_at:",
        new="if False:  # MUTANT",
        tests=("tests/test_redact.py",),
        rationale="Never truncating must return over-cap content.",
    ),
    Mutation(
        id="secrets.mask-span",
        module="agentwatch/secrets.py",
        old='parts.append(f"<REDACTED:{match.kind}>")',
        new="parts.append(text[match.start : match.end])  # MUTANT",
        tests=(
            "tests/test_secrets.py",
            "tests/test_redaction_properties.py",
            "tests/test_selftest.py",
        ),
        rationale="Copying the matched span instead of masking it must leak the secret.",
    ),
    Mutation(
        id="records.validate-before-model",
        module="agentwatch/records.py",
        old="    _validate_record_dict(data)\n",
        new="    pass  # MUTANT\n",
        tests=("tests/test_records.py", "tests/test_schema_contract.py"),
        rationale="Skipping strict validation must let a malformed record through, never coerce.",
    ),
)

# Equivalent mutants: survivors that are provably behaviour-preserving. Each must
# carry a reason a reviewer can check. Kept empty unless a real equivalent is found;
# lowering the budget is never the way to silence a survivor.
ALLOWLIST: dict[str, str] = {}


def gate_status(
    results: list[MutationResult],
    *,
    budget: int,
    allowlist: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    """Return (exit_code, unaccounted survivors) for a batch of results.

    A survivor is unaccounted unless it is in the allow-list. The gate fails when
    the unaccounted survivors exceed ``budget`` (a ratchet: lower it over time,
    never raise it to hide a new gap).
    """
    allowed = allowlist or {}
    survivors = sorted(
        result.id for result in results if result.survived and result.id not in allowed
    )
    return (1 if len(survivors) > budget else 0), survivors


def run_mutation(mutation: Mutation, *, timeout: float) -> MutationResult:
    """Apply one mutation, run its focused tests, and always restore the source."""
    path = SRC / mutation.module
    original = path.read_bytes()
    text = original.decode("utf-8")
    count = text.count(mutation.old)
    if count != 1:
        raise SystemExit(
            f"mutation {mutation.id}: anchor found {count} times in {mutation.module} "
            "(expected exactly 1); update the anchor"
        )
    try:
        path.write_text(text.replace(mutation.old, mutation.new), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *mutation.tests,
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=PKG,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Tests pass => the mutation survived (not caught). Nonzero => killed.
        return MutationResult(mutation.id, proc.returncode == 0, proc.returncode)
    finally:
        path.write_bytes(original)


# A deliberately behaviour-preserving edit (docstring) that no test can catch; used
# by --self-test to prove the gate flags an uncaught mutant.
SELF_TEST_MUTATION = Mutation(
    id="selftest.no-op-docstring",
    module="agentwatch/redact.py",
    old='"""Redaction and privacy controls.\n',
    new='"""Redaction and privacy controls (mutated docstring).\n',
    tests=("tests/test_redact.py",),
    rationale="A docstring edit is unobservable; it must survive and trip the gate.",
)


def _run_self_test(timeout: float) -> int:
    result = run_mutation(SELF_TEST_MUTATION, timeout=timeout)
    if not result.survived:
        print("self-test FAILED: a no-op mutation was reported as killed")
        return 1
    code, survivors = gate_status([result], budget=0, allowlist=ALLOWLIST)
    if code != 1 or SELF_TEST_MUTATION.id not in survivors:
        print("self-test FAILED: the gate did not fail on a surviving mutant")
        return 1
    print("self-test OK: a surviving mutant trips the gate")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=0, help="max allowed survivors")
    parser.add_argument("--only", action="append", default=[], help="run only this mutation id")
    parser.add_argument("--timeout", type=float, default=600.0, help="per-mutation seconds")
    parser.add_argument(
        "--self-test", action="store_true", help="prove the gate fails on a survivor"
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return _run_self_test(args.timeout)

    selected = [m for m in MUTATIONS if not args.only or m.id in args.only]
    if not selected:
        print(f"no mutations match {args.only}", file=sys.stderr)
        return 2

    results: list[MutationResult] = []
    for mutation in selected:
        result = run_mutation(mutation, timeout=args.timeout)
        status = "SURVIVED" if result.survived else "killed"
        print(f"[{status:8}] {mutation.id} ({mutation.rationale})")
        results.append(result)

    code, survivors = gate_status(results, budget=args.budget, allowlist=ALLOWLIST)
    killed = len(results) - sum(1 for r in results if r.survived)
    print(f"\n{killed}/{len(results)} mutants killed; budget={args.budget}")
    if code != 0:
        print("mutation gate FAILED — unaccounted survivors:", file=sys.stderr)
        for mutation_id in survivors:
            print(f"  - {mutation_id}", file=sys.stderr)
    else:
        print("mutation gate passed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
