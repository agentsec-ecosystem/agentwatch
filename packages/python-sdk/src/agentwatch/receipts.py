"""Redaction receipts (M15 S32, #237).

Privacy-by-default asks a user to trust a transformation they never see.
``verify-privacy`` proves *no secrets survived*; a **receipt** shows what the
redactor did to one record — fields kept, fields dropped/masked, and the rule id
responsible (``secrets:aws-key``, ``privacy-mode:metadata-only``,
``truncation:512``). Receipts name rules and field *paths*, never values, and are
derived at read time (nothing is added to the store).

``redact_preview`` runs a user's own sample through the active configuration and
returns the before/after pair; it never touches the store.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from agentwatch.records import AgentRecord, RecordPrivacyMode
from agentwatch.redact import PrivacyMode, RedactionConfig
from agentwatch.secrets import redact_mapping, redact_secrets
from agentwatch.store import RecordStore

_REDACTED = re.compile(r"<REDACTED:([a-z0-9-]+)>")
_TRUNCATION_MARKER = "[...]"

# Fields always present on a valid record and never content-bearing.
_BASE_KEPT = ("session_id", "agent.identity", "tool.name", "outcome", "started_at")


@dataclass(frozen=True)
class Receipt:
    """What the redactor did to one record, by field path and rule id."""

    seq: int
    kept: tuple[str, ...] = field(default_factory=tuple)
    dropped: tuple[str, ...] = field(default_factory=tuple)
    rules: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kept": list(self.kept),
            "dropped": list(self.dropped),
            "rules": list(self.rules),
        }


def _walk(path: str, value: Any, kept: list[str], dropped: list[str], rules: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _walk(f"{path}.{key}", item, kept, dropped, rules)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk(f"{path}[{index}]", item, kept, dropped, rules)
        return
    if isinstance(value, str):
        kinds = _REDACTED.findall(value)
        if kinds:
            for kind in kinds:
                rule = f"secrets:{kind}"
                if rule not in rules:
                    rules.append(rule)
            dropped.append(path)
            return
        if value.endswith(_TRUNCATION_MARKER) or _TRUNCATION_MARKER in value:
            rule = f"truncation:{len(value)}"
            if rule not in rules:
                rules.append(rule)
            kept.append(path)
            return
    kept.append(path)


def record_receipt(record: AgentRecord, *, seq: int = 0) -> Receipt:
    """Derive a receipt for one stored record (read-only)."""
    kept: list[str] = list(_BASE_KEPT)
    dropped: list[str] = []
    rules: list[str] = []

    mode = record.tool.privacy_mode
    if mode is RecordPrivacyMode.METADATA_ONLY:
        rule = "privacy-mode:metadata-only"
        rules.append(rule)

    for field_name, content in (
        ("tool.arguments", record.tool.arguments),
        ("tool.response", record.tool.response),
    ):
        if content is None:
            if mode is RecordPrivacyMode.METADATA_ONLY:
                dropped.append(field_name)
            continue
        _walk(field_name, content, kept, dropped, rules)
    if record.truncated is not None:
        fields = record.truncated.get("fields")
        if isinstance(fields, list):
            for mark in fields:
                if isinstance(mark, dict):
                    rule = f"truncation:{mark.get('rule', 'unknown')}"
                    if rule not in rules:
                        rules.append(rule)
                    field_path = mark.get("field")
                    if isinstance(field_path, str) and field_path not in dropped:
                        dropped.append(field_path)
    return Receipt(seq=seq, kept=tuple(kept), dropped=tuple(dropped), rules=tuple(rules))


def session_receipts(store: RecordStore, session_id: str) -> list[Receipt]:
    """One receipt per record of a session, in store order."""
    receipts: list[Receipt] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.session_id != session_id:
            continue
        receipts.append(record_receipt(record, seq=entry.seq))
    return receipts


# ---------------------------------------------------------------------------
# ``redact --preview`` — run a user's own sample through the active config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactPreview:
    """Before/after of one sample; nothing is stored."""

    before: str
    after: str
    rules: tuple[str, ...]


def _apply_mode(value: Any, cfg: RedactionConfig) -> Any:
    if isinstance(value, str):
        return cfg.apply(value, allowed=True)
    if isinstance(value, dict):
        return {key: _apply_mode(item, cfg) for key, item in value.items()}
    if isinstance(value, list):
        return [_apply_mode(item, cfg) for item in value]
    return value


def redact_preview(sample: str, cfg: RedactionConfig) -> RedactPreview:
    """Mask + apply the active privacy mode to ``sample``; store nothing.

    A JSON object/array sample is treated structurally; anything else is a string.
    """
    parsed: Any = sample
    try:
        candidate = json.loads(sample)
        if isinstance(candidate, (dict, list)):
            parsed = candidate
    except (json.JSONDecodeError, ValueError):
        parsed = sample

    rules: list[str] = []
    if isinstance(parsed, (dict, list)):
        masked, kinds = redact_mapping(parsed)
    else:
        masked, kinds = redact_secrets(str(parsed))
    for kind in kinds:
        rules.append(f"secrets:{kind}")
    if cfg.mode is PrivacyMode.METADATA_ONLY:
        rules.append("privacy-mode:metadata-only")
    after = _apply_mode(masked, cfg)
    if isinstance(after, (dict, list)):
        after_text = json.dumps(after, sort_keys=True, ensure_ascii=False)
    else:
        after_text = "null" if after is None else str(after)
    before_text = (
        json.dumps(parsed, sort_keys=True, ensure_ascii=False)
        if isinstance(parsed, (dict, list))
        else str(parsed)
    )
    return RedactPreview(before=before_text, after=after_text, rules=tuple(rules))
