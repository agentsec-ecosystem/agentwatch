"""``agentwatch compliance report`` — the offline compliance-report engine (M26 CMP-1).

One command renders a framework's controls as **control -> evidence command ->
verdict -> refs**, computed from the store and the active configuration, plus the
retention and checkpoint-signature status. It is offline and air-gapped (R6):
every row names a command that regenerates it, a row with no evidence fails
rather than being omitted, and the report never certifies — it states
non-conformity in plain terms. Templates live in :mod:`agentwatch.compliance_templates`
(CMP-2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentwatch.configuration import AgentwatchConfig
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"

# Frameworks CMP-2 provides templates for; the engine is framework-agnostic.
FRAMEWORKS = ("generic", "eu-ai-act-art12", "iso-42001", "iso-27001", "soc2", "nist-800-92")

STORE_REF = "docs/reference/store-format.md"
FORENSIC_REF = "docs/design/forensic-soundness.md"
IDENTITY_REF = "docs/design/agent-identity.md"
EVIDENCE_REF = "docs/reference/evidence-verifier.md"
COMPLIANCE_REF = "docs/reference/compliance.md"


@dataclass(frozen=True)
class ControlResult:
    """One compliance row: control, evidence command, verdict, refs."""

    control: str
    title: str
    evidence: str
    verdict: str
    detail: str
    refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "control": self.control,
            "title": self.title,
            "evidence": self.evidence,
            "verdict": self.verdict,
            "detail": self.detail,
            "refs": list(self.refs),
        }


@dataclass(frozen=True)
class RetentionStatus:
    """Retention configuration vs the oldest retained record."""

    retention_days: int | None
    oldest_record_days: int | None
    records: int
    status: str  # configured | overdue | unknown
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "retention_days": self.retention_days,
            "oldest_record_days": self.oldest_record_days,
            "records": self.records,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SignatureStatus:
    """Whether checkpoint signing is enabled (opt-in; never assumed)."""

    signed: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {"signed": self.signed, "detail": self.detail}


@dataclass(frozen=True)
class ComplianceReport:
    """The whole report for one framework at one moment."""

    framework: str
    installation: str
    generated_at: datetime
    controls: tuple[ControlResult, ...] = ()
    retention: RetentionStatus | None = None
    signature: SignatureStatus | None = None
    statement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "installation": self.installation,
            "generated_at": self.generated_at.isoformat(),
            "controls": [control.to_dict() for control in self.controls],
            "retention": self.retention.to_dict() if self.retention else None,
            "signature": self.signature.to_dict() if self.signature else None,
            "statement": self.statement,
        }


@dataclass(frozen=True)
class _ControlSpec:
    control: str
    title: str
    evidence: str
    refs: tuple[str, ...]
    check: Callable[[RecordStore, AgentwatchConfig, list[AgentRecord]], tuple[str, str]]


def _log_integrity(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    status = store.verify()
    if status.ok:
        return PASS, f"hash chain intact over {len(records)} record(s)"
    return FAIL, f"hash chain broken at seq {status.broken_at}"


def _retention_configured(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    days = config.store.retention_days
    if days and days > 0:
        return PASS, f"retention configured for {days} day(s)"
    return UNKNOWN, "no retention window configured"


def _redaction_default(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    mode = config.privacy.mode
    if mode == "full":
        return FAIL, "privacy.mode=full keeps raw content (non-default posture)"
    return PASS, f"privacy mode {mode} keeps content redacted"


def _checkpointing(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    if config.store.checkpoint_every:
        return PASS, f"chain checkpoints every {config.store.checkpoint_every} record(s)"
    return UNKNOWN, "chain checkpointing disabled; an operator rewrite is undetectable"


def _recording_coverage(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    return UNKNOWN, "coverage needs an independent transcript (agentwatch coverage)"


def _identity_attribution(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    attributed = sum(
        1
        for record in records
        if record.agent.principal
        or record.agent.workload_identity
        or record.agent.delegation_chain
    )
    if attributed:
        return PASS, f"{attributed} record(s) carry an on-behalf-of/workload identity"
    return UNKNOWN, "no record carries an on-behalf-of/workload identity yet"


def _evidence_bundle(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    if records:
        return PASS, "at least one session is available to bundle"
    return UNKNOWN, "no recorded session to bundle"


_CONTROLS: tuple[_ControlSpec, ...] = (
    _ControlSpec(
        "log-integrity",
        "Recorded activity is append-ordered and tamper-evident",
        "agentwatch verify-store",
        (STORE_REF, FORENSIC_REF),
        _log_integrity,
    ),
    _ControlSpec(
        "redaction-default",
        "Content is redacted before storage",
        "agentwatch verify-privacy",
        (STORE_REF,),
        _redaction_default,
    ),
    _ControlSpec(
        "retention-configured",
        "A retention window is configured",
        "agentwatch retention apply",
        (STORE_REF,),
        _retention_configured,
    ),
    _ControlSpec(
        "checkpointing",
        "Chain checkpoints bound undetected rewrites",
        "agentwatch checkpoint",
        (FORENSIC_REF,),
        _checkpointing,
    ),
    _ControlSpec(
        "recording-coverage",
        "Recording gaps are reconciled against ground truth",
        "agentwatch coverage",
        (FORENSIC_REF,),
        _recording_coverage,
    ),
    _ControlSpec(
        "identity-attribution",
        "Actions carry an on-behalf-of/workload identity",
        "agentwatch search --identity",
        (IDENTITY_REF,),
        _identity_attribution,
    ),
    _ControlSpec(
        "evidence-bundle",
        "An evidence bundle can be produced",
        "agentwatch evidence <session>",
        (EVIDENCE_REF, COMPLIANCE_REF),
        _evidence_bundle,
    ),
)


def _retention_status(
    records: list[AgentRecord], config: AgentwatchConfig, now: datetime
) -> RetentionStatus:
    days = config.store.retention_days
    oldest: int | None = None
    if records:
        oldest = max(0, int((now - min(r.started_at for r in records)).total_seconds() // 86400))
    if not days or days <= 0:
        return RetentionStatus(days, oldest, len(records), UNKNOWN, "no retention window configured")
    if oldest is not None and oldest > days:
        return RetentionStatus(
            days,
            oldest,
            len(records),
            "overdue",
            f"oldest record is {oldest}d old but retention is {days}d",
        )
    return RetentionStatus(days, oldest, len(records), "configured", "within the retention window")


_STATEMENT = (
    "This report is evidence of configuration and recorded activity for this installation. "
    "It is not a certification; it does not attest to any human's identity, and a passing row "
    "records a check agentwatch ran, not a third-party audit opinion."
)


def build_report(
    store: RecordStore,
    framework: str = "generic",
    *,
    config: AgentwatchConfig | None = None,
    now: datetime | None = None,
) -> ComplianceReport:
    """Build the offline compliance report for ``framework`` (never certifies)."""
    cfg = config or AgentwatchConfig()
    moment = now or datetime.now(timezone.utc)
    records = list(store.records())
    results: list[ControlResult] = []
    for spec in _CONTROLS:
        verdict, detail = spec.check(store, cfg, records)
        results.append(
            ControlResult(
                control=spec.control,
                title=spec.title,
                evidence=spec.evidence,
                verdict=verdict,
                detail=detail,
                refs=spec.refs,
            )
        )
    controls = tuple(results)
    signature = SignatureStatus(
        signed=False,
        detail="checkpoint signing is not enabled (opt-in); unsigned checkpoints verify integrity only",
    )
    return ComplianceReport(
        framework=framework,
        installation="this installation",
        generated_at=moment,
        controls=controls,
        retention=_retention_status(records, cfg, moment),
        signature=signature,
        statement=_STATEMENT,
    )


def render_report(report: ComplianceReport) -> str:
    """Render the report as short text (verdicts, evidence, refs)."""
    lines = [
        f"agentwatch compliance {report.framework} ({report.installation})",
        f"  generated: {report.generated_at.isoformat()}",
    ]
    for control in report.controls:
        lines.append(f"  [{control.verdict.upper()}] {control.control}: {control.title}")
        lines.append(f"    evidence: {control.evidence}")
        lines.append(f"    {control.detail}")
    if report.retention is not None:
        lines.append(
            f"  retention: {report.retention.status} "
            f"(window={report.retention.retention_days}d, oldest={report.retention.oldest_record_days}d)"
        )
    if report.signature is not None:
        signed = "signed" if report.signature.signed else "unsigned"
        lines.append(f"  checkpoints: {signed} — {report.signature.detail}")
    lines.append(f"  {report.statement}")
    return "\n".join(lines)


__all__ = [
    "FAIL",
    "FRAMEWORKS",
    "PASS",
    "UNKNOWN",
    "ComplianceReport",
    "ControlResult",
    "RetentionStatus",
    "SignatureStatus",
    "build_report",
    "render_report",
]
