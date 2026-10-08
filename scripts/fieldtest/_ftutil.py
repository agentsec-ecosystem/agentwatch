"""Shared helpers for the v0.2.0 field-test drivers (M31 31.2).

Drivers run inside the recorder container at /ft/scripts/, where `agentwatch` is
on PATH and the store lives at /data/agentwatch. Each driver is a fail-closed
script: it prints `ok: ...` on success and exits non-zero on any failure, so a
case that cannot prove its claim fails rather than passing silently.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STORE = Path("/data/agentwatch/records.jsonl")
QUARANTINE = Path("/data/agentwatch/quarantine.jsonl")


def run(cmd: str | list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, shell=isinstance(cmd, str), capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"driver: command failed ({proc.returncode}): {cmd}")
    return proc


def records() -> list[dict]:
    if not STORE.exists():
        return []
    out: list[dict] = []
    for line in STORE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def fixture(kind: str) -> Path:
    return Path(f"/ft/fixtures/{kind}")


def arg(argv: list[str], name: str, default: str | None = None) -> str | None:
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


def ok(msg: str) -> None:
    print(f"ok: {msg}")


def fail(msg: str) -> None:
    print(f"fail: {msg}", file=sys.stderr)
    raise SystemExit(1)
