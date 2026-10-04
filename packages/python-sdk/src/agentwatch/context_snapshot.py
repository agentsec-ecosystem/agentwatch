"""Session-start environment snapshot (M19 S16/S29, PRD 35).

"What did the agent do?" is half an answer without "to what, and as whom?" At
``SessionStart`` we capture, once per session, metadata only:

* the VCS revision the agent acted on — ``git`` commit, branch, dirty tree, or
  an honest ``none`` / ``unavailable``;
* the OS principal it ran as — uid/username, hostname, pid/ppid, TTY, and an
  ``interactive | headless | ci`` classification;
* the harness and OS/arch, and the agentwatch version.

No env-var *values*, no home paths, no remote URLs are ever captured. The
snapshot is metadata the operator can correlate, not content the agent saw.
Everything degrades to an honest value and never raises: a hook must never block.
"""

from __future__ import annotations

import contextlib
import getpass
import os
import platform
import socket
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

VCS_GIT = "git"
VCS_NONE = "none"
VCS_UNAVAILABLE = "unavailable"

CONTEXT_INTERACTIVE = "interactive"
CONTEXT_HEADLESS = "headless"
CONTEXT_CI = "ci"

# Conventional CI env-var *names* only — a value is never read or stored.
CI_ENV_NAMES = frozenset(
    {
        "CI",
        "CONTINUOUS_INTEGRATION",
        "BUILD_NUMBER",
        "BUILDKITE",
        "CIRCLECI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "TEAMCITY_VERSION",
        "TRAVIS",
    }
)

_GIT_TIMEOUT_SECONDS = 2.0


def classify_context(env: Mapping[str, str] | None = None, *, tty: bool | None = None) -> str:
    """Classify the run as ``ci``, ``headless``, or ``interactive``.

    CI wins over TTY (a CI job is ``ci`` even if it happens to have one); no TTY
    is ``headless``; otherwise ``interactive``.
    """
    source = os.environ if env is None else env
    if any(name in source for name in CI_ENV_NAMES):
        return CONTEXT_CI
    is_tty = sys.stdin.isatty() if tty is None else tty
    return CONTEXT_INTERACTIVE if is_tty else CONTEXT_HEADLESS


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def git_snapshot(cwd: str | Path | None) -> dict[str, Any]:
    """The VCS state of ``cwd``: ``git`` (with revision), ``none``, or ``unavailable``.

    ``none`` means "we looked and it is not a repository"; ``unavailable`` means
    "we could not look" (no cwd, no ``git``, or a failure) — the two are never
    conflated.
    """
    if not cwd:
        return {"vcs": VCS_UNAVAILABLE}
    directory = str(cwd)
    if not os.path.isdir(directory):
        return {"vcs": VCS_UNAVAILABLE}

    inside = _run_git(["rev-parse", "--is-inside-work-tree"], directory)
    if inside is None:
        return {"vcs": VCS_UNAVAILABLE}
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"vcs": VCS_NONE}

    commit = _run_git(["rev-parse", "HEAD"], directory)
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], directory)
    status = _run_git(["status", "--porcelain"], directory)
    snapshot: dict[str, Any] = {"vcs": VCS_GIT}
    if commit is not None and commit.returncode == 0 and commit.stdout.strip():
        snapshot["commit"] = commit.stdout.strip()
    if branch is not None and branch.returncode == 0 and branch.stdout.strip():
        snapshot["branch"] = branch.stdout.strip()
    if status is not None and status.returncode == 0:
        snapshot["dirty"] = bool(status.stdout.strip())
    return snapshot


def principal_snapshot(
    env: Mapping[str, str] | None = None, *, tty: bool | None = None
) -> dict[str, Any]:
    """The OS principal the process runs as (pid/uid/host/context). Metadata only."""
    is_tty = sys.stdin.isatty() if tty is None else tty
    principal: dict[str, Any] = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "tty": is_tty,
        "context": classify_context(env, tty=is_tty),
    }
    if hasattr(os, "getuid"):  # pragma: no branch - not on Windows
        principal["uid"] = os.getuid()
    with contextlib.suppress(OSError, KeyError):
        principal["username"] = getpass.getuser()
    with contextlib.suppress(OSError):
        principal["hostname"] = socket.gethostname()
    return principal


def environment_snapshot(
    cwd: str | None = None,
    *,
    include_principal: bool = True,
    env: Mapping[str, str] | None = None,
    tty: bool | None = None,
    harness: str = "claude-code",
    version: str | None = None,
) -> dict[str, Any]:
    """Build the metadata-only session-start snapshot (S16 + S29 merged)."""
    if version is None:
        from agentwatch import __version__

        version = __version__
    snapshot: dict[str, Any] = {
        "vcs": git_snapshot(cwd),
        "harness": {"name": harness},
        "os": {"system": platform.system(), "arch": platform.machine()},
        "agentwatch": {"version": version},
    }
    principal = principal_snapshot(env, tty=tty)
    snapshot["context"] = principal["context"]
    if include_principal:
        snapshot["principal"] = principal
    return snapshot


def filter_snapshot(snapshot: Mapping[str, Any], *, include_principal: bool) -> dict[str, Any]:
    """Return the snapshot with the OS-principal block dropped when disallowed.

    The ``interactive | headless | ci`` classification is retained: it is about
    the container, not the person.
    """
    result = dict(snapshot)
    if not include_principal:
        result.pop("principal", None)
    return result


__all__ = [
    "CI_ENV_NAMES",
    "CONTEXT_CI",
    "CONTEXT_HEADLESS",
    "CONTEXT_INTERACTIVE",
    "VCS_GIT",
    "VCS_NONE",
    "VCS_UNAVAILABLE",
    "classify_context",
    "environment_snapshot",
    "filter_snapshot",
    "git_snapshot",
    "principal_snapshot",
]
