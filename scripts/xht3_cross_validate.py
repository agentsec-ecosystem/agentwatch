#!/usr/bin/env python3
"""XHT-3 cross-parser validation for the Codex rollout reader (M27, #352).

Our reader's understanding of the Codex rollout format is cross-checked against
**two independent OSS parsers** on the same golden fixture — a divergence is a
failing test (or a documented interpretation gap). The parsers are pinned to a
commit and attributed (MIT); the CI job clones them and runs this script:

    python scripts/xht3_cross_validate.py --parsers-dir /tmp/xht3-parsers

Exit code is non-zero on any divergence not listed in ``KNOWN_GAPS``.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from agentwatch.codex_rollout import read_rollout  # noqa: E402

# Pinned, attributed (MIT) independent parsers.
PINS: dict[str, dict[str, str]] = {
    "agent_history": {
        "repo": "https://github.com/kvsankar/agent-history",
        "commit": "56c766ad182689c887e575a1a387dfec2e4a5ebd",
        "license": "MIT",
    },
    "agent_ouija": {
        "repo": "https://github.com/kylesnowschwartz/agent-ouija",
        "commit": "c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc",
        "license": "MIT",
    },
}

# Documented interpretation gaps (none currently): a divergence listed here is a
# known, cited difference, not a silent failure.
KNOWN_GAPS: set[str] = set()

DEFAULT_FIXTURES = REPO / "packages" / "python-sdk" / "tests" / "fixtures" / "codex-cli" / "golden"

_GO_HARNESS = '''package main

import (
	"bufio"
	"encoding/json"
	"os"

	rollout "github.com/kylesnowschwartz/agent-ouija/codex/rollout"
)

func main() {
	f, err := os.Open(os.Args[1])
	if err != nil {
		panic(err)
	}
	defer f.Close()
	counts := map[string]int{}
	session, cwd := "", ""
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 16*1024*1024)
	for sc.Scan() {
		e, ok := rollout.ParseEntry(sc.Bytes())
		if !ok {
			counts["!invalid"]++
			continue
		}
		counts[e.Type+"/"+e.Payload.Type]++
		if e.Type == "session_meta" {
			session, cwd = e.Payload.ID, e.Payload.Cwd
		}
	}
	out, _ := json.Marshal(map[string]any{"session_id": session, "cwd": cwd, "counts": counts})
	os.Stdout.Write(out)
}
'''


def ours(path: Path) -> dict[str, Any]:
    read = read_rollout(path)
    calls = [
        (record.span_id, record.tool.name)
        for record in read.records
        if record.step_type is not None and record.step_type.value == "act"
    ]
    counts = Counter(
        f"{record.step_type.value}:{record.tool.name}"
        for record in read.records
        if record.step_type is not None
    )
    return {
        "session_id": read.session_id,
        "cwd": next((r.project for r in read.records if r.project), None),
        "calls": sorted(calls),
        "counts": dict(counts),
    }


def _load_agent_history(parsers_dir: Path) -> Any:
    module_path = parsers_dir / "agent-history" / "agent-history"
    loader = importlib.machinery.SourceFileLoader("xht3_agent_history", str(module_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def agent_history(path: Path, parsers_dir: Path) -> dict[str, Any]:
    module = _load_agent_history(parsers_dir)
    messages, meta = module.codex_read_jsonl_messages(path)
    calls = [
        (message["raw_payload"].get("call_id"), message["raw_payload"].get("name"))
        for message in messages
        if message.get("is_tool_call")
    ]
    meta = meta or {}
    return {
        "session_id": meta.get("id"),
        "cwd": meta.get("cwd"),
        "calls": sorted(calls),
    }


def agent_ouija(path: Path, parsers_dir: Path) -> dict[str, Any]:
    module_dir = parsers_dir / "agent-ouija"
    with tempfile.NamedTemporaryFile("w", suffix=".go", delete=False, encoding="utf-8") as handle:
        handle.write(_GO_HARNESS)
        harness = handle.name
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, trusted harness
        ["go", "run", harness, str(path)],
        cwd=module_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="XHT-3 Codex cross-parser validation")
    parser.add_argument("--parsers-dir", type=Path, default=Path(".xht3-parsers"))
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args(argv)

    fixtures = sorted(args.fixtures.glob("*.jsonl"))
    if not fixtures:
        print(f"xht3: no fixtures in {args.fixtures}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for fixture in fixtures:
        mine = ours(fixture)
        history = agent_history(fixture, args.parsers_dir)
        ouija = agent_ouija(fixture, args.parsers_dir)
        fixture_failures: list[str] = []

        if mine["calls"] != history["calls"]:
            fixture_failures.append(
                f"{fixture.name}: tool calls differ ours={mine['calls']} theirs={history['calls']}"
            )
        if mine["session_id"] != ouija["session_id"] or mine["cwd"] != ouija["cwd"]:
            fixture_failures.append(
                f"{fixture.name}: session id/cwd differ ours={mine['session_id']}/{mine['cwd']}"
            )
        ours_io = sum(
            count
            for key, count in mine["counts"].items()
            if key.split(":", 1)[0] in ("act", "observe")
        )
        theirs_io = sum(
            count
            for key, count in ouija["counts"].items()
            if key.split("/")[-1]
            in (
                "function_call",
                "function_call_output",
                "custom_tool_call",
                "custom_tool_call_output",
            )
        )
        if ours_io != theirs_io:
            fixture_failures.append(
                f"{fixture.name}: tool I/O count differs ours={ours_io} theirs={theirs_io}"
            )
        failures.extend(fixture_failures)
        if not fixture_failures:
            print(f"xht3: {fixture.name}: ours ok; agent-history + agent-ouija cross-checked")

    failures = [f for f in failures if f not in KNOWN_GAPS]
    if failures:
        for failure in failures:
            print(f"xht3: DIVERGENCE {failure}", file=sys.stderr)
        return 1
    print("xht3: no divergence across two independent parsers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
