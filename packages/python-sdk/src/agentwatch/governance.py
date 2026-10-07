"""``agentwatch governance notice`` — a notice from the live effective config (M29 ACC-2, #449).

PRD 56 §ACC-2, design [access-and-governance](../../../../docs/design/access-and-governance.md).
Every adopter has to publish a monitoring notice and a DPIA, and every adopter
rewrites them. This renders the factual part — what is recorded, what is not, who
can see it, retention, and how to request erasure — from the *live effective
configuration*, so the notice cannot drift from what the tool actually does.

Two honesty rules:

* **every statement maps to a config key or a documented guarantee**, and a
  statement with an unknown config key fails loudly at construction;
* **unbackable claims are omitted and listed as refused** — e.g. "recorded
  activity never leaves this machine" is refused the moment an export sink or an
  event sink is enabled.

This is not legal advice; it is a config-derived fact sheet with a counsel-review
banner. The DPIA starter lives at ``docs/compliance/dpia-starter.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentwatch.configuration import _DEFAULTS, AgentwatchConfig

NOT_LEGAL_ADVICE = (
    "This notice is generated from this installation's live effective configuration. "
    "It is not legal advice; have counsel review it before relying on it for any "
    "compliance or employee-monitoring obligation."
)

# The section order the notice renders in.
SECTIONS = (
    "recorded",
    "not-recorded",
    "access",
    "retention",
    "erasure",
    "storage",
    "export",
    "sinks",
)


@dataclass(frozen=True)
class NoticeStatement:
    """One factual statement, tied to the config key or guarantee that backs it."""

    section: str
    text: str
    backing: str

    def to_dict(self) -> dict[str, Any]:
        return {"section": self.section, "text": self.text, "backing": self.backing}


@dataclass(frozen=True)
class RefusedClaim:
    """A claim the config cannot back, kept visible rather than silently dropped."""

    claim: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"claim": self.claim, "reason": self.reason}


@dataclass(frozen=True)
class Notice:
    """The rendered notice: backed statements, refused claims, and the banner."""

    statements: tuple[NoticeStatement, ...]
    refused: tuple[RefusedClaim, ...]
    banner: str = NOT_LEGAL_ADVICE

    def to_dict(self) -> dict[str, Any]:
        return {
            "banner": self.banner,
            "statements": [statement.to_dict() for statement in self.statements],
            "refused": [refused.to_dict() for refused in self.refused],
        }


def _flatten(prefix: str, data: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(_flatten(dotted, value))
        else:
            keys.add(dotted)
    return keys


def known_config_keys() -> frozenset[str]:
    """Every dotted config key in the schema (the notice's allowed backing)."""
    return frozenset(_flatten("", _DEFAULTS))


@dataclass(frozen=True)
class _Candidate:
    section: str
    text: str
    backing: str


def build_notice(config: AgentwatchConfig) -> Notice:
    """Render the notice from a resolved effective configuration."""
    mode = config.privacy.mode
    candidates: list[_Candidate] = [
        _Candidate(
            "recorded",
            "Each agent action records the tool, outcome, timing, and agent identity;"
            f" content fidelity is '{mode}'.",
            "privacy.mode",
        ),
        _Candidate(
            "recorded",
            "On-behalf-of principals are keyed-hashed; plaintext is stored only under"
            " privacy.mode=full.",
            "privacy.mode",
        ),
    ]
    if mode == "metadata-only":
        candidates.append(
            _Candidate(
                "not-recorded",
                "Prompt and tool-argument content is not stored (privacy.mode=metadata-only).",
                "privacy.mode",
            )
        )
    else:
        candidates.append(
            _Candidate(
                "not-recorded",
                f"Content the harness exposes may be stored at fidelity '{mode}' (privacy.mode).",
                "privacy.mode",
            )
        )
    candidates.append(
        _Candidate(
            "access",
            "Fleet reads follow the least-privileged role x data-class model; every cross-user"
            " read is recorded, and you can list who read your records (agentwatch access log).",
            "guarantee:access-model",
        )
    )
    candidates.append(
        _Candidate(
            "retention",
            f"Records are kept for {config.store.retention_days} day(s) (store.retention_days),"
            " then tombstoned (never hard-deleted).",
            "store.retention_days",
        )
    )
    candidates.append(
        _Candidate(
            "erasure",
            "You can request erasure of a session's records; `agentwatch purge <session> --yes`"
            " tombstones them while preserving the chain.",
            "guarantee:erasure-tombstone",
        )
    )
    candidates.append(
        _Candidate(
            "storage",
            f"Records are stored locally at {config.store.path} (store.path).",
            "store.path",
        )
    )
    if config.export.enabled:
        endpoint = config.export.otlp_endpoint or "unset"
        candidates.append(
            _Candidate(
                "export",
                f"Records may leave this machine via the configured OTLP endpoint ({endpoint})"
                " (export.enabled=true).",
                "export.enabled",
            )
        )
    else:
        candidates.append(
            _Candidate(
                "export",
                "OTLP export is disabled; records are not sent anywhere (export.enabled=false).",
                "export.enabled",
            )
        )
    candidates.append(
        _Candidate(
            "sinks",
            (
                "Security events may be forwarded to configured sinks (sinks.enabled=true)."
                if config.sinks.enabled
                else "Security-event forwarding is disabled (sinks.enabled=false)."
            ),
            "sinks.enabled",
        )
    )

    known = known_config_keys()
    for candidate in candidates:
        if not candidate.backing.startswith("guarantee:") and candidate.backing not in known:
            raise ValueError(f"unknown config key {candidate.backing!r} in notice statement")

    refused: list[RefusedClaim] = [
        RefusedClaim(
            "This notice establishes that this installation is compliant with GDPR, the EU AI"
            " Act, or any other regulation.",
            "agentwatch makes no legal determination; compliance requires counsel and, for"
            " evidence, an audit (see the compliance report — it is not a certification).",
        )
    ]
    if config.export.enabled or config.sinks.enabled:
        reasons: list[str] = []
        if config.export.enabled:
            reasons.append("export.enabled is on (OTLP endpoint)")
        if config.sinks.enabled:
            reasons.append("sinks.enabled is on (event forwarding)")
        refused.append(
            RefusedClaim(
                "Recorded activity never leaves this machine.",
                " and ".join(reasons) + ".",
            )
        )
    if mode != "metadata-only":
        refused.append(
            RefusedClaim(
                "No content is ever recorded.",
                f"privacy.mode={mode} stores content at that fidelity.",
            )
        )

    return Notice(
        statements=tuple(
            NoticeStatement(c.section, c.text, c.backing) for c in candidates
        ),
        refused=tuple(refused),
    )


def render_notice(notice: Notice) -> str:
    """Render a notice as short, copyable text with the banner and refusals."""
    lines = ["agentwatch governance notice", "", notice.banner, ""]
    for section in SECTIONS:
        rows = [statement for statement in notice.statements if statement.section == section]
        if not rows:
            continue
        lines.append(section.upper())
        for statement in rows:
            lines.append(f"  - {statement.text}  [{statement.backing}]")
        lines.append("")
    if notice.refused:
        lines.append("REFUSED TO CLAIM")
        for refused in notice.refused:
            lines.append(f"  - {refused.claim} — {refused.reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "NOT_LEGAL_ADVICE",
    "SECTIONS",
    "Notice",
    "NoticeStatement",
    "RefusedClaim",
    "build_notice",
    "known_config_keys",
    "render_notice",
]