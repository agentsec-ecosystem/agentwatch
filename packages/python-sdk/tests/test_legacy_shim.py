"""DD-12 compatibility: the legacy ``agent_exec_trace`` import path still resolves.

Existing instrumentation imports the shipped package name; the shim must keep
``import agent_exec_trace`` and ``from agent_exec_trace.<submodule> import ...``
working after the namespace rename.
"""

from __future__ import annotations

import importlib


def test_legacy_package_resolves_to_agentwatch() -> None:
    legacy = importlib.import_module("agent_exec_trace")
    current = importlib.import_module("agentwatch")

    assert legacy is current


def test_legacy_submodule_resolves_to_agentwatch_submodule() -> None:
    legacy_context = importlib.import_module("agent_exec_trace.context")
    current_context = importlib.import_module("agentwatch.context")

    assert legacy_context.RunContext is current_context.RunContext


def test_legacy_import_preserves_canonical_module_metadata() -> None:
    importlib.import_module("agent_exec_trace.context")
    current_context = importlib.import_module("agentwatch.context")

    assert current_context.__spec__ is not None
    assert current_context.__spec__.name == "agentwatch.context"
