"""Redaction self-test that gates export (M4 4.6, DD-09).

Runs a fixed corpus of secret-bearing tool arguments through the masking +
privacy-mode pipeline and asserts no raw secret survives. If any leaks, export
stays blocked (F6): never export unredacted data (R7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping

# Fixed corpus: arguments that *must* be masked before storage/export.
SELF_TEST_CORPUS: tuple[dict[str, Any], ...] = (
    {"token": "sk-LEAK-abcdefgh"},
    {"card": "4111 1111 1111 1111"},
    {"db": "postgres://admin:pgLEAK@db:5432/app"},
    {"note": "reach me at leaker@example.com"},
)

# Raw substrings that must never survive the pipeline.
_LEAK_MARKERS: tuple[str, ...] = (
    "sk-LEAK-abcdefgh",
    "4111 1111 1111 1111",
    "pgLEAK",
    "leaker@example.com",
)


@dataclass(frozen=True)
class SelfTestResult:
    """Outcome of the redaction self-test."""

    passed: bool
    checked: int
    leaks: tuple[str, ...]


def _apply_mode(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, dict):
        return {key: _apply_mode(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_apply_mode(item, cfg) for item in value]
    return value


def run_redaction_self_test(cfg: RedactionConfig | None = None) -> SelfTestResult:
    """Mask the corpus, apply the mode, and report any surviving secret."""
    config = cfg or RedactionConfig(mode=PrivacyMode.TRUNCATED, capture_tool_args=True)
    leaks: list[str] = []
    for item in SELF_TEST_CORPUS:
        masked, _ = redact_mapping(item)
        text = json.dumps(_apply_mode(masked, config))
        for marker in _LEAK_MARKERS:
            if marker in text and marker not in leaks:
                leaks.append(marker)
    return SelfTestResult(passed=not leaks, checked=len(SELF_TEST_CORPUS), leaks=tuple(leaks))


def export_allowed(cfg: RedactionConfig | None = None) -> bool:
    """Whether export may proceed: only when the self-test passes (DD-09)."""
    return run_redaction_self_test(cfg).passed
