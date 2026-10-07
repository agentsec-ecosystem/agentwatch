"""`agentwatch governance notice` + DPIA starter (M29 ACC-2, #449).

PRD 56 §ACC-2: a notice rendered from the **live effective config** — what is
recorded, what is not, who can see it, retention, and how to request erasure —
where every statement maps to a config key or a documented guarantee. Anything the
config cannot back is omitted and listed as refused, and the whole thing carries a
"not legal advice" banner.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.config_explain import explain_config
from agentwatch.configuration import (
    AgentwatchConfig,
    ExportSection,
    PrivacySection,
    SinksSection,
)
from agentwatch.governance import (
    NOT_LEGAL_ADVICE,
    Notice,
    NoticeStatement,
    build_notice,
    render_notice,
)

REPO = Path(__file__).resolve().parents[3]


def _default() -> AgentwatchConfig:
    return AgentwatchConfig()


def _effective_keys() -> set[str]:
    return {item.key for item in explain_config(paths=[], env={}, cli_overrides={})}


def test_every_statement_maps_to_a_config_key_or_a_guarantee() -> None:
    notice = build_notice(_default())
    known = _effective_keys()

    assert notice.statements
    for statement in notice.statements:
        assert statement.backing.startswith("guarantee:") or statement.backing in known, (
            statement.backing
        )


def test_notice_declares_it_is_not_legal_advice() -> None:
    notice = build_notice(_default())

    assert notice.banner == NOT_LEGAL_ADVICE
    assert "not legal advice" in render_notice(notice).lower()


def test_retention_statement_matches_the_configured_window() -> None:
    cfg = replace(_default(), store=replace(_default().store, retention_days=45))
    notice = build_notice(cfg)

    statement = next(s for s in notice.statements if s.backing == "store.retention_days")
    assert "45" in statement.text


def test_notice_states_who_can_see_records_from_the_access_model() -> None:
    notice = build_notice(_default())

    assert any(statement.section == "access" for statement in notice.statements)


def test_egress_claim_is_refused_when_export_is_enabled() -> None:
    cfg = replace(
        _default(),
        export=ExportSection(enabled=True, otlp_endpoint="https://sink.example", format="otel-genai"),
    )
    notice = build_notice(cfg)
    rendered = render_notice(notice)

    assert not any("never leaves" in statement.text.lower() for statement in notice.statements)
    assert any("never leaves" in refused.claim.lower() for refused in notice.refused)
    # The refusal is shown as refused, never asserted as a fact statement.
    assert "REFUSED TO CLAIM" in rendered
    assert "never leaves" in rendered.lower()
    # The export path itself is disclosed, backed by its key.
    assert any(statement.backing == "export.enabled" for statement in notice.statements)


def test_egress_claim_is_backed_when_export_is_disabled() -> None:
    notice = build_notice(_default())

    assert not any("never leaves" in refused.claim.lower() for refused in notice.refused)
    export = next(s for s in notice.statements if s.backing == "export.enabled")
    assert "disabled" in export.text.lower()


def test_notice_always_refuses_a_legal_determination() -> None:
    notice = build_notice(_default())

    assert any("complian" in refused.claim.lower() for refused in notice.refused)


def test_non_metadata_mode_discloses_content_and_refuses_no_content() -> None:
    cfg = replace(_default(), privacy=PrivacySection(mode="full"))
    notice = build_notice(cfg)

    assert any("full" in statement.text for statement in notice.statements)
    assert any("no content is ever recorded" in refused.claim.lower() for refused in notice.refused)


def test_sinks_enabled_refuses_the_egress_claim() -> None:
    cfg = replace(_default(), sinks=SinksSection(enabled=True, targets=("https://siem.example",)))
    notice = build_notice(cfg)

    statement = next(s for s in notice.statements if s.backing == "sinks.enabled")
    assert "forwarded" in statement.text.lower()
    assert any("never leaves" in refused.claim.lower() for refused in notice.refused)
    assert any("sinks" in refused.reason.lower() for refused in notice.refused)


def test_render_notice_skips_empty_sections() -> None:
    notice = Notice(
        statements=(NoticeStatement("retention", "kept for 1 day", "store.retention_days"),),
        refused=(),
    )

    text = render_notice(notice)

    assert "RETENTION" in text
    assert "RECORDED" not in text
    assert "REFUSED TO CLAIM" not in text
    assert "not legal advice" in text.lower()


def test_cli_governance_notice_renders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--set", f"store.path={tmp_path}", "governance", "notice"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "not legal advice" in out.lower()
    assert "retention" in out.lower()


def test_cli_governance_notice_json_lists_refused_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        [
            "--set",
            f"store.path={tmp_path}",
            "--set",
            "export.enabled=true",
            "--set",
            "export.otlp_endpoint=https://sink.example",
            "governance",
            "notice",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["banner"] == NOT_LEGAL_ADVICE
    assert all("backing" in statement for statement in payload["statements"])
    assert any("never leaves" in refused["claim"].lower() for refused in payload["refused"])


def test_dpia_starter_carries_a_counsel_review_banner() -> None:
    doc = REPO / "docs" / "compliance" / "dpia-starter.md"

    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "counsel" in text.lower()
    assert "not legal advice" in text.lower()
