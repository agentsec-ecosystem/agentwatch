#!/usr/bin/env python3
"""M31 31.3 — run the local-console Playwright spec against a live console (LUI-1).

Starts `agentwatch ui` (loopback, per-launch token) via the SDK module (the
host has no `agentwatch` entry point on PATH), parses its URL from stdout with a
**bounded** select() read, runs `apps/web/tests/e2e/console.spec.ts`, then stops
the console. Both waits are bounded: a console that never prints its URL and a
Playwright run that stalls both fail the case instead of hanging it. Exit code is
the Playwright result, so a red console spec fails the case rather than passing.
"""
from __future__ import annotations

import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = int(os.environ.get("FT_CONSOLE_PORT", "0"))  # 0 = ephemeral (no port clashes)
CONSOLE_BOOT_TIMEOUT = 20.0
PLAYWRIGHT_TIMEOUT = 180.0
URL_RE = re.compile(r"http://127\.0\.0\.1:\d+/\?token=[A-Za-z0-9_-]+")


def _console_env() -> dict[str, str]:
    env = dict(os.environ)
    sdk = str(REPO / "packages/python-sdk/src")
    prior = env.get("PYTHONPATH")
    env["PYTHONPATH"] = sdk if not prior else f"{sdk}{os.pathsep}{prior}"
    env["PYTHONUNBUFFERED"] = "1"  # the console prints its URL then serves; flush it
    return env


def _wait_for_url(proc: subprocess.Popen[str], deadline: float) -> str | None:
    """Read the console's stdout until its token URL appears, bounded by deadline."""
    assert proc.stdout is not None
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        ready, _, _ = select.select([proc.stdout], [], [], remaining)
        if not ready:
            return None
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                return None
            continue
        match = URL_RE.search(line)
        if match:
            return match.group(0)


def main() -> int:
    env = _console_env()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "agentwatch", "ui",
            "--host", "127.0.0.1", "--port", str(PORT), "--no-open",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        url = _wait_for_url(proc, time.time() + CONSOLE_BOOT_TIMEOUT)
        if not url:
            print("console did not start", file=sys.stderr)
            return 1
        run_env = dict(
            env,
            FT_CONSOLE_URL=url,
            FT_SCREENSHOT_DIR=str(REPO / "docs/assets/screenshots"),
        )
        playwright = REPO / "apps/web" / "node_modules" / ".bin" / "playwright"
        try:
            return subprocess.call(
                [str(playwright), "test", "tests/e2e/console.spec.ts"],
                cwd=str(REPO / "apps/web"),
                env=run_env,
                timeout=PLAYWRIGHT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"playwright timed out after {PLAYWRIGHT_TIMEOUT:.0f}s", file=sys.stderr)
            return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
