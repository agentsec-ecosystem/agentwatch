"""Secret/PII detection and masking (M4 4.2, R7).

This is the trust boundary that guarantees no secret or PII is ever persisted
(DD-06). Every string destined for a store/export passes through
:func:`redact_secrets`; mapping-shaped tool arguments pass through
:func:`redact_mapping`, which also masks values whose *key name* is sensitive
(``*_TOKEN`` / ``*_KEY`` / ``*_SECRET`` / ``*_PASSWORD``).

Matches are replaced with ``<REDACTED:kind>`` and the kinds that fired are
returned so the adapter can emit a ``secret-detected`` security event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Priority order: earlier patterns win overlaps and order the returned kinds.
SECRET_KINDS: tuple[str, ...] = (
    "private-key",
    "api-key",
    "oauth-bearer",
    "jwt",
    "cloud-secret",
    "connection-string",
    "credit-card",
    "ssn",
    "email",
    "phone",
    "env-secret",
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "api-key",
        re.compile(
            r"(?:sk-[A-Za-z0-9_\-]{8,}"
            r"|gh[pousr]_[A-Za-z0-9]{20,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
            r"|AIza[0-9A-Za-z_\-]{20,})"
        ),
    ),
    ("oauth-bearer", re.compile(r"Bearer\s+[A-Za-z0-9._\-]+")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("cloud-secret", re.compile(r"ya29\.[A-Za-z0-9_\-]+")),
    (
        "connection-string",
        re.compile(
            r"(?:postgres(?:ql)?|mongodb(?:\+srv)?|redis|mysql|amqp)://"
            r"[^\s:@/]+:[^\s@/]+@[^\s/]+"
        ),
    ),
    ("credit-card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\+[1-9]\d{6,14}\b")),
)

_ENV_KEY = re.compile(r"(?i).*(?:_TOKEN|_KEY|_SECRET|_PASSWORD)$")

_PRIORITY = {kind: index for index, (kind, _) in enumerate(_PATTERNS)}


@dataclass(frozen=True)
class SecretMatch:
    """One detected secret span in a string."""

    kind: str
    start: int
    end: int


def _luhn_ok(candidate: str) -> bool:
    digits = [int(ch) for ch in candidate if ch.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def detect(text: str) -> list[SecretMatch]:
    """Return non-overlapping secret spans in ``text``, ordered by position."""
    candidates: list[tuple[int, int, int, str]] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if kind == "credit-card" and not _luhn_ok(match.group()):
                continue
            candidates.append((match.start(), match.end(), _PRIORITY[kind], kind))

    candidates.sort(key=lambda item: (item[0], item[2]))
    chosen: list[SecretMatch] = []
    last_end = -1
    for start, end, _priority, kind in candidates:
        if start >= last_end:
            chosen.append(SecretMatch(kind=kind, start=start, end=end))
            last_end = end
    return chosen


def redact_secrets(text: str) -> tuple[str, tuple[str, ...]]:
    """Mask every detected secret in ``text``; return masked text and kinds."""
    matches = detect(text)
    if not matches:
        return text, ()
    parts: list[str] = []
    last = 0
    for match in matches:
        parts.append(text[last : match.start])
        parts.append(f"<REDACTED:{match.kind}>")
        last = match.end
    parts.append(text[last:])
    found = {match.kind for match in matches}
    kinds = tuple(kind for kind in SECRET_KINDS if kind in found)
    return "".join(parts), kinds


def redact_mapping(value: Any) -> tuple[Any, tuple[str, ...]]:
    """Recursively mask secrets in a JSON-shaped value.

    Values under a sensitive key name are masked wholesale as ``env-secret``.
    Returns the masked value and the deduped kinds that fired.
    """
    kinds: list[str] = []

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            result: dict[Any, Any] = {}
            for key, item in node.items():
                if isinstance(key, str) and isinstance(item, str) and _ENV_KEY.match(key):
                    result[key] = "<REDACTED:env-secret>"
                    kinds.append("env-secret")
                else:
                    result[key] = _walk(item)
            return result
        if isinstance(node, list):
            return [_walk(item) for item in node]
        if isinstance(node, str):
            masked, found = redact_secrets(node)
            kinds.extend(found)
            return masked
        return node

    masked_value = _walk(value)
    found_set = set(kinds)
    ordered = tuple(kind for kind in SECRET_KINDS if kind in found_set)
    return masked_value, ordered
