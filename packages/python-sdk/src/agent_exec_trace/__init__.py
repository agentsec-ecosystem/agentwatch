"""Compatibility shim for the legacy ``agent_exec_trace`` import path (DD-12).

The shipped package name is preserved so existing instrumentation keeps working
after the namespace rename. Importing this package yields :mod:`agentwatch`, and
submodule imports (``agent_exec_trace.tracer``, ``agent_exec_trace.spans``, ...)
resolve to the *same* module objects as ``agentwatch.*``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType

import agentwatch

_LEGACY = __name__
_NEW = "agentwatch"

# ``import agent_exec_trace`` yields the agentwatch package.
sys.modules[_LEGACY] = agentwatch


class _LegacyAliasLoader(importlib.abc.Loader):
    """Hand back the already-imported ``agentwatch`` submodule unchanged."""

    _CANONICAL_ATTRS = ("__spec__", "__loader__", "__package__")

    def __init__(self, module: ModuleType) -> None:
        self._module = module
        # Import machinery rewrites these on the shared module object; snapshot
        # them so the canonical agentwatch.* metadata is restored afterwards.
        self._canonical = {
            name: getattr(module, name, None) for name in self._CANONICAL_ATTRS
        }

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return self._module

    def exec_module(self, module: ModuleType) -> None:
        for name, value in self._canonical.items():
            setattr(module, name, value)


class _LegacyAliasFinder(importlib.abc.MetaPathFinder):
    """Map ``agent_exec_trace.<sub>`` onto ``agentwatch.<sub>``."""

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(_LEGACY + "."):
            return None
        target_name = _NEW + fullname[len(_LEGACY) :]
        try:
            module = importlib.import_module(target_name)
        except ImportError:
            return None
        return importlib.util.spec_from_loader(fullname, _LegacyAliasLoader(module))


sys.meta_path.insert(0, _LegacyAliasFinder())
