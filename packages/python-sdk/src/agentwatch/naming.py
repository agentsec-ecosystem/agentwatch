"""Install-integrity naming guard (M25 NAM-1, PRD 48, ADR-0026).

The import/CLI name ``agentwatch`` is shared by five or more unrelated projects,
so ``pip install agentwatch`` installs a different, unaudited package. This module
detects that situation and produces a loud warning; the fully-qualified install is
``pip install agentsec-agentwatch``. See ``docs/reference/namesake-faq.md``.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable, Mapping

# Our distribution name (what the fully-qualified install pulls) and the shared
# import name whose namesakes we must detect.
DISTRIBUTION_NAME = "agentsec-agentwatch"
IMPORT_NAME = "agentwatch"
FULL_INSTALL = f"pip install {DISTRIBUTION_NAME}"

_WARNING = (
    "warning: the 'agentwatch' module was provided by a distribution other than "
    f"'{DISTRIBUTION_NAME}'. This is likely a namesake package, not agentwatch. "
    f"Install the real one with: {FULL_INSTALL}"
)
# Public spelling so callers/tests can assert the message without touching a private name.
NAMESAKE_WARNING = _WARNING


def distribution_warning(
    packages: Mapping[str, list[str]] | None = None,
) -> str | None:
    """Return a loud warning when ``agentwatch`` is provided by a foreign distribution.

    ``packages`` defaults to :func:`importlib.metadata.packages_distributions`.
    A missing mapping entry means "cannot tell" and returns ``None`` (never a false
    warning); an entry that names only foreign distributions returns the warning.
    """
    mapping = (
        importlib.metadata.packages_distributions()
        if packages is None
        else packages
    )
    distributions = mapping.get(IMPORT_NAME)
    if not distributions:
        return None
    if DISTRIBUTION_NAME in distributions:
        return None
    return _WARNING


def install_guard(
    warn: Callable[[str], None],
    *,
    detector: Callable[[], str | None] = distribution_warning,
) -> bool:
    """Emit the warning (if any) through ``warn``; return whether it fired.

    Safe to call from ``--version`` / ``init`` / ``doctor``: it never raises and
    never blocks — a hook must exit 0.
    """
    try:
        warning = detector()
    except Exception:  # pragma: no cover - defensive: metadata lookup must not break a hook
        return False
    if warning:
        warn(warning)
        return True
    return False


__all__ = [
    "DISTRIBUTION_NAME",
    "FULL_INSTALL",
    "IMPORT_NAME",
    "NAMESAKE_WARNING",
    "distribution_warning",
    "install_guard",
]