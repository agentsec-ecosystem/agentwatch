"""End-to-end hook wall-clock measurement (M29 DEP-3, #443; PRD 50).

``design/performance-budget.md`` budgets the in-process step; the latency a
developer actually feels is the **process-spawn cost of a fresh hook interpreter**,
and agentwatch installs two hook processors per tool call
(``design/claude-code-hook-contract.md``). This module measures the real
end-to-end wall-clock of ``agentwatch-hook pre`` against a draining socket,
per OS, and publishes it with a user-visible budget.

Windows is **blocked**: agentwatch's hook transport is a Unix domain socket and
the named-pipe transport is re-pointed to M31 (WIN-1), so a Windows number is
reported as blocked, never silently measured.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agentwatch.perf import PerfStats, summarize

# A tool call fires PreToolUse + PostToolUse, each a fresh interpreter process.
HOOKS_PER_TOOL_CALL = 2
# The session overhead figure quoted to operators.
SESSION_CALLS = 500
# Per single hook invocation, p99. Two hooks => this x2 per tool call. Chosen so
# the user-visible statement is "adds < 500 ms per tool call at p99"; the process
# spawn dominates and is machine-dependent, so the drift band absorbs variance.
HOOK_P99_BUDGET_MS = 250.0
DRIFT_TOLERANCE = 3.0
DRIFT_FLOOR_MS = 5.0

BEGIN_MARKER = "<!-- BEGIN GENERATED HOOK E2E -->"
END_MARKER = "<!-- END GENERATED HOOK E2E -->"


def detect_os(platform: str | None = None) -> str:
    """Map ``sys.platform`` to a published OS name."""
    value = sys.platform if platform is None else platform
    if value == "darwin":
        return "macos"
    if value.startswith("win"):
        return "windows"
    return "linux"


def _src_path() -> str:
    return str(Path(__file__).resolve().parents[1])


def _default_payload() -> dict[str, object]:
    return {
        "session_id": "perf-hook",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "tool_use_id": "perf-hook-1",
        "timestamp": "2026-01-02T03:04:05+00:00",
    }


class _DrainServer:
    """A short-path UDS listener that accepts and drains hook frames."""

    def __init__(self, socket_dir: Path | str | None = None) -> None:
        self._owns_dir = socket_dir is None
        # AF_UNIX paths are length-limited; keep the socket directory short.
        base = (
            Path(socket_dir)
            if socket_dir is not None
            else Path(tempfile.mkdtemp(prefix="aw-hookperf-", dir="/tmp"))
        )
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "hook.sock"
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> _DrainServer:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self.path))
        self._sock.listen(64)
        self._sock.settimeout(0.1)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            with conn, contextlib.suppress(OSError):
                conn.settimeout(0.1)
                while not self._stop.is_set() and conn.recv(65536):
                    pass

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
        self.path.unlink(missing_ok=True)
        if self._owns_dir:
            shutil.rmtree(self.path.parent, ignore_errors=True)


@dataclass(frozen=True)
class HookWallclock:
    """One OS's end-to-end hook latency distribution."""

    os_name: str
    stats: PerfStats
    budget_ms: float
    blocked: bool = False
    block_reason: str | None = None

    @property
    def within_budget(self) -> bool:
        return not self.blocked and self.stats.p99_ms <= self.budget_ms

    @property
    def per_tool_call_ms(self) -> float:
        return self.stats.p99_ms * HOOKS_PER_TOOL_CALL

    def session_overhead_ms(self, calls: int = SESSION_CALLS) -> float:
        """The wall-clock a ``calls``-call session adds (unblocked path)."""
        return self.per_tool_call_ms * calls

    def session_overhead_seconds(self, calls: int = SESSION_CALLS) -> float:
        return self.session_overhead_ms(calls) / 1000.0


def measure_hook_wallclock(
    *,
    command: str | None = None,
    args: Sequence[str] = ("pre",),
    payload: Mapping[str, object] | None = None,
    iterations: int = 20,
    budget_ms: float = HOOK_P99_BUDGET_MS,
    os_name: str | None = None,
    socket_dir: Path | str | None = None,
    timeout: float = 30.0,
) -> HookWallclock:
    """Measure the end-to-end wall-clock of one hook invocation per iteration.

    ``command`` defaults to the resolved ``agentwatch-hook`` entry point (with a
    draining socket so a delivery is measured, not a spool write). Windows is
    reported blocked without measuring.
    """
    resolved_os = os_name or detect_os()
    if resolved_os == "windows":
        return HookWallclock(
            os_name="windows",
            stats=PerfStats(iterations=0, mean_ms=0.0, p50_ms=0.0, p99_ms=0.0, max_ms=0.0),
            budget_ms=budget_ms,
            blocked=True,
            block_reason=(
                "Windows hook wall-clock is blocked on WIN-1: the hook transport is a "
                "Unix domain socket and the named-pipe transport is re-pointed to M31"
            ),
        )
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    if command is None:
        from agentwatch.install import resolve_hook_command

        resolved = resolve_hook_command()
        argv = [resolved.command, *resolved.args_prefix, *args]
    else:
        argv = [command, *args]
    base_payload = dict(payload or _default_payload())

    samples: list[float] = []
    with _DrainServer(socket_dir) as server:
        env = {
            **os.environ,
            "AGENTWATCH_SOCKET": str(server.path),
            "PYTHONPATH": _src_path() + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        for index in range(iterations):
            message = json.dumps({**base_payload, "_iter": index}).encode("utf-8")
            start = time.perf_counter()
            with contextlib.suppress(subprocess.SubprocessError):
                subprocess.run(
                    argv,
                    input=message,
                    capture_output=True,
                    env=env,
                    timeout=timeout,
                    check=False,
                )
            samples.append((time.perf_counter() - start) * 1000.0)

    return HookWallclock(os_name=resolved_os, stats=summarize(samples), budget_ms=budget_ms)


def evaluate_hook(
    wallclock: HookWallclock,
    baseline_p99: float | None,
    *,
    tolerance: float = DRIFT_TOLERANCE,
    floor_ms: float = DRIFT_FLOOR_MS,
) -> tuple[int, list[str]]:
    """Return ``(exit_code, violations)`` for one OS's measurement."""
    if wallclock.blocked:
        return 0, []
    violations: list[str] = []
    if wallclock.stats.p99_ms > wallclock.budget_ms:
        violations.append(
            f"{wallclock.os_name}: hook p99 {wallclock.stats.p99_ms:.1f} ms > "
            f"budget {wallclock.budget_ms:.1f} ms"
        )
    if baseline_p99 is not None:
        threshold = max(baseline_p99 * tolerance, floor_ms)
        if wallclock.stats.p99_ms > threshold:
            violations.append(
                f"{wallclock.os_name}: hook p99 {wallclock.stats.p99_ms:.1f} ms > drift "
                f"threshold {threshold:.1f} ms (baseline {baseline_p99:.1f} ms)"
            )
    return (1 if violations else 0, violations)


def render_block(wallclocks: Sequence[HookWallclock]) -> str:
    """Render the deterministic end-to-end hook table (markers included)."""
    lines = [
        BEGIN_MARKER,
        "| OS | hook p50 (ms) | hook p99 (ms) | per tool call p99 (ms) | budget (ms) | "
        "500-call session (s) |",
        "|---|---|---|---|---|---|",
    ]
    for wallclock in sorted(wallclocks, key=lambda item: item.os_name):
        if wallclock.blocked:
            label = "blocked (WIN-1)" if "WIN-1" in (wallclock.block_reason or "") else (
                wallclock.block_reason or "blocked"
            )
            lines.append(
                f"| {wallclock.os_name} | blocked | blocked | blocked | "
                f"{wallclock.budget_ms:.0f} | {label} |"
            )
        else:
            lines.append(
                f"| {wallclock.os_name} | {wallclock.stats.p50_ms:.1f} | "
                f"{wallclock.stats.p99_ms:.1f} | {wallclock.per_tool_call_ms:.1f} | "
                f"{wallclock.budget_ms:.0f} | {wallclock.session_overhead_seconds():.1f} |"
            )
    lines.append(END_MARKER)
    return "\n".join(lines)


def replace_marker_block(text: str, block: str) -> str:
    """Replace (or append) the generated hook block inside ``text``."""
    if BEGIN_MARKER in text and END_MARKER in text:
        start = text.index(BEGIN_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        return text[:start] + block + text[end:]
    return text.rstrip("\n") + "\n\n" + block + "\n"


__all__ = [
    "BEGIN_MARKER",
    "DRIFT_FLOOR_MS",
    "DRIFT_TOLERANCE",
    "END_MARKER",
    "HOOK_P99_BUDGET_MS",
    "HOOKS_PER_TOOL_CALL",
    "SESSION_CALLS",
    "HookWallclock",
    "detect_os",
    "evaluate_hook",
    "measure_hook_wallclock",
    "render_block",
    "replace_marker_block",
]
