"""Consent-first A2A proxy install + byte-identical restore (M29 A2A-1 #364).

Install re-points an A2A client's ``a2aAgents`` entries at the local
interposition proxy, backing up the exact original bytes so ``uninstall``
restores the file identically. Fail closed: an unparseable config is refused and
a file that changed after install is left untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentwatch import a2a_config


def _target(tmp_path: Path) -> a2a_config.A2aConfigTarget:
    return a2a_config.resolve_a2a_scope("project", cwd=tmp_path)


def _command() -> a2a_config.A2aProxyCommand:
    return a2a_config.A2aProxyCommand(command="agentwatch", args_prefix=("a2a-proxy",))


def test_install_repoints_a_stdio_agent_and_backs_up_bytes(tmp_path: Path) -> None:
    target = _target(tmp_path)
    original = (
        b'{\n  "a2aAgents": {"scheduler": {"command": "scheduler", "args": ["--serve"]}}\n}\n'
    )
    target.path.write_bytes(original)

    report = a2a_config.install_a2a_proxy(target, proxy_command=_command())

    assert report.repointed == ("scheduler",)
    assert report.backup_path is not None
    assert report.backup_path.read_bytes() == original
    data = __import__("json").loads(target.path.read_text())
    entry = data["a2aAgents"]["scheduler"]
    assert entry["command"] == "agentwatch"
    assert entry["args"] == ["a2a-proxy", "--agent", "scheduler", "--", "scheduler", "--serve"]
    assert a2a_config.a2a_proxy_installed(target)


def test_uninstall_restores_the_exact_original_bytes(tmp_path: Path) -> None:
    target = _target(tmp_path)
    original = (
        b'{\n  "a2aAgents": {"scheduler": {"command": "scheduler", "args": []}},\n  "other": 1\n}\n'
    )
    target.path.write_bytes(original)
    a2a_config.install_a2a_proxy(target, proxy_command=_command())

    report = a2a_config.uninstall_a2a_proxy(target)

    assert report.restored
    assert target.path.read_bytes() == original
    assert not a2a_config.a2a_proxy_installed(target)


def test_uninstall_deletes_a_file_it_created(tmp_path: Path) -> None:
    target = _target(tmp_path)
    a2a_config.install_a2a_proxy(target, proxy_command=_command())

    report = a2a_config.uninstall_a2a_proxy(target)

    assert report.deleted
    assert not target.path.exists()


def test_uninstall_refuses_when_the_file_changed_since_install(tmp_path: Path) -> None:
    target = _target(tmp_path)
    target.path.write_bytes(b'{"a2aAgents": {"scheduler": {"command": "scheduler", "args": []}}}')
    a2a_config.install_a2a_proxy(target, proxy_command=_command())
    target.path.write_bytes(target.path.read_bytes() + b"\n")

    report = a2a_config.uninstall_a2a_proxy(target)

    assert not report.restored
    assert report.reason is not None and "changed" in report.reason
    assert a2a_config.a2a_proxy_installed(target)


def test_unparseable_config_is_refused(tmp_path: Path) -> None:
    target = _target(tmp_path)
    target.path.write_bytes(b"not json")

    with pytest.raises(a2a_config.A2aConfigError):
        a2a_config.install_a2a_proxy(target, proxy_command=_command())


def test_uninstall_without_a_manifest_is_a_noop(tmp_path: Path) -> None:
    report = a2a_config.uninstall_a2a_proxy(_target(tmp_path))

    assert not report.restored
    assert report.reason == "not installed"


def test_resolve_a2a_proxy_command_falls_back_to_module() -> None:
    command = a2a_config.resolve_a2a_proxy_command("/nonexistent/python")

    assert command.command == "/nonexistent/python"
    assert command.args_prefix == ("-m", "agentwatch.a2a_proxy")