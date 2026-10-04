"""Standalone redactor tests (M21 S13, #269)."""

from __future__ import annotations

import io
import json

import pytest

from agentwatch.cli.main import main
from agentwatch.redactor import (
    FINDINGS_SCHEMA,
    RedactorError,
    findings_to_dict,
    redact,
)

# Built at runtime so no provider-shaped literal sits in the source.
SECRET = "sk-" + "abcdefghijklmnop"
TEXT = f"export TOKEN={SECRET} now"


def test_masks_the_same_as_the_write_path() -> None:
    result = redact(TEXT, "hashed")

    assert SECRET not in str(result.output)
    assert "<REDACTED:api-key>" in str(result.output)


def test_findings_never_contain_a_value() -> None:
    result = redact(TEXT, "hashed")

    assert result.findings
    finding = result.findings[0]
    assert finding.kind == "api-key"
    assert SECRET not in json.dumps(findings_to_dict(result.findings))


def test_findings_document_schema() -> None:
    document = findings_to_dict(redact(TEXT, "hashed").findings)
    assert document["schema"] == FINDINGS_SCHEMA
    assert set(document["findings"][0]) == {"kind", "path", "start", "end"}


def test_empty_input_has_no_findings() -> None:
    result = redact("", "hashed")
    assert result.output == ""
    assert result.findings == ()


def test_unknown_mode_errors() -> None:
    with pytest.raises(RedactorError, match="unknown mode"):
        redact("hello", "nonsense")


def test_metadata_only_emits_no_content() -> None:
    result = redact(TEXT, "metadata-only")

    assert result.output == ""
    assert any(finding.kind == "privacy-mode" for finding in result.findings)


def test_structured_value_paths() -> None:
    value = {"tool_input": {"command": f"echo {SECRET}"}}

    result = redact(value, "hashed")

    assert isinstance(result.output, dict)
    assert SECRET not in json.dumps(result.output)
    assert result.findings[0].path == "$.tool_input.command"


def test_cli_filter_masks_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(TEXT))

    rc = main(["redact", "--mode", "hashed", "--json"])

    assert rc == 0
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert "<REDACTED:api-key>" in captured.out
    findings = json.loads(captured.err)
    assert findings["findings"][0]["kind"] == "api-key"


def test_cli_preview_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["redact", "--preview", f"x={SECRET}", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert SECRET not in payload["after"]
