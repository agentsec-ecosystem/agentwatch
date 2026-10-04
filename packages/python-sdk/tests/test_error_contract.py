"""The one machine-readable error contract (PRD 38 §Q8, issue #225).

Every CLI failure emits exactly one envelope; the published exit-code table is
generated from the catalog; and the code carries a stable `code`/`hint`/`doc_url`.
"""

from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stderr
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from agentwatch import errors
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

cli_main = import_module("agentwatch.cli.main")

REPO = Path(__file__).resolve().parents[3]
ERRORS_DOC = REPO / "docs" / "reference" / "errors.md"
BEGIN = "<!-- BEGIN GENERATED: exit-codes -->"
END = "<!-- END GENERATED: exit-codes -->"
SUBCOMMANDS = cli_main.subcommands()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from a temp dir with no user/project config or AGENTWATCH_* env."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key in list(os.environ):
        if key.startswith("AGENTWATCH_"):
            monkeypatch.delenv(key, raising=False)
    return tmp_path


def _run(argv: list[str]) -> tuple[int, str]:
    """Call the CLI, tolerating argparse's SystemExit, and capture stderr."""
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        try:
            code = cli_main.main(argv)
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, buffer.getvalue()


def _envelope(err: str) -> dict[str, Any]:
    """Return the last JSON error envelope on stderr."""
    for line in reversed(err.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "error" in payload:
            return payload
    raise AssertionError(f"no error envelope on stderr: {err!r}")


def _generated_block(doc: str) -> str:
    _, _, rest = doc.partition(BEGIN)
    block, _, _ = rest.partition(END)
    return block.strip()


def test_generated_exit_code_table_matches_the_catalog() -> None:
    assert _generated_block(ERRORS_DOC.read_text(encoding="utf-8")) == errors.render_table().strip()


def test_catalog_is_unique_and_well_formed() -> None:
    codes = [spec.code for spec in errors.CATALOG]
    assert len(codes) == len(set(codes))
    anchors = {errors.doc_url(spec.code).rsplit("#", 1)[1] for spec in errors.CATALOG}
    assert len(anchors) == len(codes)
    for spec in errors.CATALOG:
        assert spec.exit_code in {1, 2, 3}
        assert spec.summary and spec.hint


def test_exit_constants_derive_from_the_catalog() -> None:
    assert errors.exit_code(errors.ErrorCode.USAGE) == 2
    assert errors.exit_code(errors.ErrorCode.CONFIG) == 2
    assert errors.exit_code(errors.ErrorCode.NOT_IMPLEMENTED) == 3
    assert errors.exit_code(errors.ErrorCode.FAILED) == 1
    assert errors.exit_code("E_DOES_NOT_EXIST") == errors.exit_code(errors.ErrorCode.FAILED)


def test_envelope_has_exactly_the_contract_fields() -> None:
    payload = errors.envelope(errors.ErrorCode.CONFIG, "boom", "fix it")
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "hint", "doc_url"}
    assert payload["error"]["code"] == errors.ErrorCode.CONFIG
    assert payload["error"]["message"] == "boom"
    assert payload["error"]["hint"] == "fix it"
    assert payload["error"]["doc_url"].endswith("#e-config")


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (3, "not implemented in v0.1.0", errors.ErrorCode.NOT_IMPLEMENTED),
        (2, "configuration error: unknown key", errors.ErrorCode.CONFIG),
        (2, "usage: agentwatch ...", errors.ErrorCode.USAGE),
        (1, "agentwatch: chain broken at seq 1", errors.ErrorCode.CHAIN_BROKEN),
        (1, "agentwatch: no records for session s", errors.ErrorCode.SESSION_NOT_FOUND),
        (1, "agentwatch: daemon not reachable", errors.ErrorCode.DAEMON_UNREACHABLE),
        (1, "agentwatch: refusing to purge without --yes", errors.ErrorCode.CONFIRMATION_REQUIRED),
        (1, "something unexpected", errors.ErrorCode.FAILED),
    ],
)
def test_classify_maps_status_and_message(status: int, message: str, expected: str) -> None:
    assert errors.classify(status, message) == expected


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_every_subcommand_failure_emits_an_envelope(command: str) -> None:
    code, err = _run([command, "--definitely-not-a-flag"])

    assert code != 0
    envelope = _envelope(err)
    assert set(envelope["error"]) == {"code", "message", "hint", "doc_url"}
    assert envelope["error"]["code"] == errors.ErrorCode.USAGE


def test_configuration_error_code(isolated: Path) -> None:
    code, err = _run(["--set", "not.a.real.key=1", "status"])

    assert code == errors.exit_code(errors.ErrorCode.CONFIG)
    assert _envelope(err)["error"]["code"] == errors.ErrorCode.CONFIG


def test_not_implemented_code() -> None:
    code, err = _run(["migrate"])

    assert code == errors.exit_code(errors.ErrorCode.NOT_IMPLEMENTED)
    assert _envelope(err)["error"]["code"] == errors.ErrorCode.NOT_IMPLEMENTED


def test_session_not_found_code(isolated: Path) -> None:
    code, err = _run(["replay", "session-123"])

    assert code == errors.exit_code(errors.ErrorCode.SESSION_NOT_FOUND)
    assert _envelope(err)["error"]["code"] == errors.ErrorCode.SESSION_NOT_FOUND


def test_chain_broken_code(isolated: Path) -> None:
    store_path = isolated / "records.jsonl"
    store = RecordStore(store_path, durability="none")
    store.append(
        AgentRecord(
            session_id="s",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )
    lines = store_path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[1] = json.dumps(envelope)
    store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    code, err = _run(["--set", f"store.path={isolated}", "verify-store"])

    assert code == errors.exit_code(errors.ErrorCode.CHAIN_BROKEN)
    assert _envelope(err)["error"]["code"] == errors.ErrorCode.CHAIN_BROKEN


def test_success_emits_no_envelope() -> None:
    code, err = _run(["--version"])

    assert code == 0
    assert '"error"' not in err
