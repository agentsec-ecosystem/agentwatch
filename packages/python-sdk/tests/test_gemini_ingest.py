"""Gemini CLI native-OTel ingest recipe tests (M25 GEM-1, #305).

Gemini CLI ships built-in OTel (`.gemini/settings.json` telemetry). The recipe is
settings/`outfile` -> `ingest --format otel`, with **mandatory** redaction because
`logPrompts` defaults true (ADR-0022). This asserts a captured telemetry file
ingests to validated records with secrets masked, and that the recipe ships.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentwatch.ingest import transcode_otel
from agentwatch.records import SecurityEventType, validate_record
from agentwatch.redact import redaction_config_from_mode

RECIPE = Path(__file__).resolve().parents[3] / "docs" / "guides" / "gemini-native-telemetry.md"


def _gemini_payload() -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "gemini-cli"}},
                        {"key": "session.id", "value": {"stringValue": "gem-sess-1"}},
                        {"key": "user.email", "value": {"stringValue": "dev@example.com"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "gsp-1",
                                "traceId": "gtrace-1",
                                "name": "execute_tool",
                                "startTimeUnixNano": "1767000000000000000",
                                "endTimeUnixNano": "1767000000050000000",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "execute_tool"},
                                    },
                                    {
                                        "key": "gen_ai.tool.name",
                                        "value": {"stringValue": "run_shell"},
                                    },
                                    {
                                        "key": "gen_ai.agent.name",
                                        "value": {"stringValue": "gemini"},
                                    },
                                    {
                                        "key": "gen_ai.tool.args",
                                        "value": {
                                            "stringValue": "export TOKEN=sk-abcdefgh1234"
                                        },
                                    },
                                ],
                            }
                        ]
                    }
                ],
            }
        ]
    }


def test_gemini_payload_ingests_and_validates() -> None:
    records, problems = transcode_otel(_gemini_payload(), source="gemini")

    assert not problems
    assert records
    for record in records:
        validate_record(record.to_dict())
    assert records[0].tool.name == "run_shell"


def test_logprompts_path_is_redacted() -> None:
    records, _ = transcode_otel(
        _gemini_payload(), source="gemini", redaction=redaction_config_from_mode("full")
    )

    dumped = " ".join(str(record.to_dict()) for record in records)
    assert "sk-abcdefgh1234" not in dumped
    assert any(
        record.security_event is not None
        and record.security_event.type is SecurityEventType.SECRET_DETECTED
        for record in records
    )


def test_recipe_documentation_ships() -> None:
    assert RECIPE.exists(), "GEM-1 requires the Gemini native-OTel recipe doc"
    text = RECIPE.read_text(encoding="utf-8")
    assert "otlpEndpoint" in text or "outfile" in text
    assert "logPrompts" in text
    assert "ingest" in text