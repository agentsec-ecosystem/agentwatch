"""Least-privilege file posture (M12 F5, PRD 28).

Records are behavior evidence; on a shared machine they must not be
world-readable. The store directory is created ``0700`` and its files ``0600`` at
creation, and :func:`mode_of` lets the doctor/health surface a loose mode rather
than hiding it.
"""

from __future__ import annotations

import contextlib
import os
import stat
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600


def _chmod(path: Path, mode: int) -> None:
    with contextlib.suppress(OSError):  # pragma: no cover - platform/permission specific
        os.chmod(path, mode)


def secure_dir(path: Path) -> None:
    """Create ``path`` (parents included) and force directory mode ``0700``."""
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, DIR_MODE)


def secure_file(path: Path) -> None:
    """Force an existing file to mode ``0600`` (no-op when absent)."""
    if path.exists():
        _chmod(path, FILE_MODE)


def mode_of(path: Path) -> int | None:
    """Return the permission bits of ``path`` (e.g. ``0o600``), or None if absent."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def is_private(path: Path, *, directory: bool = False) -> bool:
    """Whether ``path`` has the expected private mode (no group/other bits)."""
    mode = mode_of(path)
    if mode is None:
        return True  # absent is not a leak
    expected = DIR_MODE if directory else FILE_MODE
    return mode == expected


def render_mode(mode: int | None) -> str:
    """Render a mode as ``0o600`` for humans."""
    return "-" if mode is None else oct(mode)
