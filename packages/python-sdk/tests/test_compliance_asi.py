"""OWASP Agentic (ASI + AST10) coverage report (M29 ASI-1, #451).

One row per ASI risk (ASI01–ASI10) plus an Agentic Skills Top-10 section; every
row names what the record evidences, a regenerating command (or "not evidenced"),
what it cannot evidence, and a fidelity tier. Nothing claims prevention, the
non-certification statement is included, and every evidenced row's command runs
in the executable-docs gate.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from agentwatch.compliance import FRAMEWORKS, build_report, render_report
from agentwatch.configuration import AgentwatchConfig
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

REPO = Path(__file__).resolve().parents[3]
ASI_DOC = REPO / "docs" / "compliance" / "owasp-asi-2026.md"
CHECK_DOCS = REPO / "scripts" / "check_docs_commands.py"
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

ASI_FRAMEWORK = "owasp-asi-2026"
ASI_IDS = [f"ASI{n:02d}" for n in range(1, 11)]
AST_IDS = [f"AST{n:02d}" for n in range(1, 11)]
ASI_SECTION = "OWASP Top 10 for Agentic Applications 2026"
AST_SECTION = "OWASP Agentic Skills Top 10"
TIERS = {"evidenced", "signal", "not evidenced"}
_PREVENTION = re.compile(r"prevent(s|ion|ing)?\b|certif(y|ies|cation)", re.IGNORECASE)


def _record() -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="worker", principal="human@corp.example"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=NOW,
    )


def _store(tmp_path: Path) -> RecordStore:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    return store


def _report(tmp_path: Path):
    return build_report(_store(tmp_path), ASI_FRAMEWORK, config=AgentwatchConfig(), now=NOW)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _prefix(evidence: str) -> str:
    assert evidence.startswith("agentwatch ")
    return evidence[len("agentwatch ") :].split(" <", 1)[0].strip()


def test_framework_is_registered() -> None:
    assert ASI_FRAMEWORK in FRAMEWORKS


def test_all_ten_asi_rows_are_present_with_the_required_fields(tmp_path: Path) -> None:
    report = _report(tmp_path)
    asi = [c for c in report.controls if c.section == ASI_SECTION]

    assert [c.control for c in asi] == ASI_IDS
    for control in asi:
        assert control.title, f"{control.control}: no 'what it evidences' statement"
        assert control.evidence, f"{control.control}: no evidence"
        assert control.cannot_evidence, f"{control.control}: no 'cannot evidence' statement"
        assert control.tier in TIERS, f"{control.control}: bad tier {control.tier!r}"
        assert control.refs, f"{control.control}: no refs"
        assert control.verdict in {"evidenced", "not evidenced"}
        if control.tier == "not evidenced":
            assert control.evidence == "not evidenced"


def test_ast10_section_is_present(tmp_path: Path) -> None:
    report = _report(tmp_path)
    ast = [c for c in report.controls if c.section == AST_SECTION]

    assert [c.control for c in ast] == AST_IDS
    assert all(c.cannot_evidence for c in ast)
    assert all(c.tier == "not evidenced" for c in ast)


def test_no_row_claims_prevention_or_certification(tmp_path: Path) -> None:
    report = _report(tmp_path)
    for control in report.controls:
        text = f"{control.title} {control.detail} {control.cannot_evidence}"
        assert not _PREVENTION.search(text), f"{control.control}: prevention/certification language"
    assert "not a certification" in report.statement.lower()


def test_report_json_and_text_carry_the_coverage_fields(tmp_path: Path) -> None:
    report = _report(tmp_path)
    payload = report.to_dict()
    json.dumps(payload)
    first = payload["controls"][0]
    assert first["tier"] and first["cannot_evidence"] and first["section"]

    text = render_report(report)
    assert ASI_FRAMEWORK in text
    assert "ASI01" in text


def test_cli_owasp_asi_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir)

    from agentwatch.cli.main import main

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "compliance",
            "report",
            "--framework",
            ASI_FRAMEWORK,
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["framework"] == ASI_FRAMEWORK
    controls = payload["controls"]
    assert {c["control"] for c in controls} >= set(ASI_IDS) | set(AST_IDS)


def test_every_evidenced_row_command_runs_in_the_docs_gate(tmp_path: Path) -> None:
    assert ASI_DOC.exists(), f"missing {ASI_DOC}"
    checker = _load(CHECK_DOCS, "check_docs_commands")
    blocks = checker.extract_blocks(ASI_DOC.read_text(encoding="utf-8"), ASI_DOC)
    scripts = "\n".join(block.script for block in blocks)
    assert any("compliance report --framework owasp-asi-2026" in s for s in scripts.splitlines())

    report = _report(tmp_path)
    for control in report.controls:
        if control.tier == "not evidenced":
            continue
        assert _prefix(control.evidence) in scripts, (
            f"{control.control}: {control.evidence!r} is not run in the executable-docs gate"
        )


def test_asi_doc_has_executable_blocks() -> None:
    checker = _load(CHECK_DOCS, "check_docs_commands_blocks")
    blocks = checker.extract_blocks(ASI_DOC.read_text(encoding="utf-8"), ASI_DOC)
    assert any(block.mode == "run" for block in blocks)