"""The redactor as a reusable, standalone primitive (M21 S13, PRD 37).

``agentwatch.secrets`` is the most defensible asset in the repo — deterministic,
corpus-tested, and the foundation of the "0 leaks" claim — but it was reachable
only inside the write path. This module exposes it as a public library and a
``redact < in > out`` filter so agentpolicy, agentdrill, and agentcomply reuse
*one* redaction implementation instead of four.

The public API is **experimental in v0.1.0** (it may change) and is committed at
v1.0, the same policy as the store format (J1). Findings name a kind and a
location, **never a value** (G1's rule). There is no LLM and no egress.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentwatch.redact import PrivacyMode, redaction_config_from_mode
from agentwatch.secrets import detect, redact_secrets

EXPERIMENTAL = True
FINDINGS_SCHEMA = "agentwatch-redaction-findings/1"

_MODE_VALUES = ("metadata-only", "truncated", "hashed", "full")


class RedactorError(ValueError):
    """Raised for an unknown mode — never a silent default."""


@dataclass(frozen=True)
class Finding:
    """One redaction, by kind and location — never the matched value."""

    kind: str
    path: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class Redaction:
    """The masked output plus its findings."""

    output: Any
    findings: tuple[Finding, ...]

    @property
    def changed(self) -> bool:
        return bool(self.findings)


def _mode_of(mode: str | PrivacyMode) -> str:
    value = mode.value if isinstance(mode, PrivacyMode) else str(mode)
    value = value.replace("_", "-")
    if value not in _MODE_VALUES:
        raise RedactorError(
            f"unknown mode {value!r}; expected one of {', '.join(sorted(_MODE_VALUES))}"
        )
    return value


def _redact_string(text: str, mode: str, path: str) -> tuple[str, list[Finding]]:
    findings: list[Finding] = []
    for match in detect(text):
        findings.append(Finding(kind=match.kind, path=path, start=match.start, end=match.end))
    masked, _kinds = redact_secrets(text)
    if mode == "metadata-only":
        # No content is emitted at all; the length reveals only that it existed.
        if text:
            findings.append(Finding(kind="privacy-mode", path=path, start=0, end=len(text)))
        return "", findings
    if mode == "truncated":
        applied = redaction_config_from_mode(mode).apply(masked, allowed=True)
        return ("" if applied is None else applied), findings
    return masked, findings


def _redact_value(value: Any, mode: str, path: str, findings: list[Finding]) -> Any:
    if isinstance(value, str):
        masked, local = _redact_string(value, mode, path)
        findings.extend(local)
        return masked
    if isinstance(value, Mapping):
        return {
            key: _redact_value(item, mode, f"{path}.{key}", findings) for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_value(item, mode, f"{path}[{index}]", findings)
            for index, item in enumerate(value)
        ]
    return value


def redact(value: Any, mode: str | PrivacyMode = "truncated") -> Redaction:
    """Mask secrets (and apply ``mode``) to a string or a JSON-shaped value.

    Secrets are always masked regardless of mode (DD-06); the mode only decides
    how much non-secret content is emitted.
    """
    resolved = _mode_of(mode)
    findings: list[Finding] = []
    output = _redact_value(value, resolved, "$", findings)
    return Redaction(output=output, findings=tuple(findings))


def findings_to_dict(findings: tuple[Finding, ...]) -> dict[str, Any]:
    """The published findings document (kind + location, never a value)."""
    return {"schema": FINDINGS_SCHEMA, "findings": [finding.to_dict() for finding in findings]}


__all__ = [
    "EXPERIMENTAL",
    "FINDINGS_SCHEMA",
    "Finding",
    "Redaction",
    "RedactorError",
    "findings_to_dict",
    "redact",
]
