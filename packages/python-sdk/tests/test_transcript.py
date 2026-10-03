"""Tests for the transcript usage extractor (M5 A5)."""

from __future__ import annotations

import json
from pathlib import Path

from agentwatch.transcript import extract_usage


def _line(message: dict[str, object]) -> str:
    return json.dumps({"type": "assistant", "message": message})


def test_extract_usage_sums_tokens_and_model(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(
        "\n".join(
            [
                _line(
                    {
                        "model": "claude-x",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cache_read_input_tokens": 2,
                            "cache_creation_input_tokens": 1,
                        },
                    }
                ),
                _line({"model": "claude-x", "usage": {"input_tokens": 3, "output_tokens": 4}}),
            ]
        ),
        encoding="utf-8",
    )

    summary = extract_usage(path)

    assert summary.tokens == 25
    assert summary.model == "claude-x"


def test_extract_usage_never_leaks_content(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    secret = "CANARY-sk-abcdefgh"
    path.write_text(
        _line(
            {
                "model": "m",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "content": [{"type": "text", "text": secret}],
            }
        ),
        encoding="utf-8",
    )

    summary = extract_usage(path)

    assert summary.tokens == 2
    assert secret not in repr(summary)


def test_extract_usage_missing_file_is_empty(tmp_path: Path) -> None:
    summary = extract_usage(tmp_path / "nope.jsonl")

    assert summary.tokens == 0
    assert summary.model is None


def test_extract_usage_ignores_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(
        "not json\n" + _line({"model": "m", "usage": {"input_tokens": 7, "output_tokens": 0}}),
        encoding="utf-8",
    )

    assert extract_usage(path).tokens == 7
