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
from agentwatch.holds import active_holds, hold_records
from agentwatch.oversight import build_oversight
from agentwatch.recorder_state import last_state
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"

# Coverage-framework verdicts (ASI-1): a row is either backed by a regenerating
# command or states plainly that the record cannot evidence it. These are not
# control verdicts and never imply prevention or certification.
EVIDENCED = "evidenced"
NOT_EVIDENCED = "not evidenced"
# The literal a coverage row states when no command regenerates it.
NO_EVIDENCE = NOT_EVIDENCED

# Frameworks CMP-2 provides templates for; the engine is framework-agnostic.
# ``owasp-asi-2026`` (ASI-1) is a coverage map, not a control catalog.
ASI_FRAMEWORK = "owasp-asi-2026"
ASI_SECTION = "OWASP Top 10 for Agentic Applications 2026"
AST_SECTION = "OWASP Agentic Skills Top 10"
FRAMEWORKS = (
    "generic",
    "eu-ai-act-art12",
    "eu-ai-act-art14",
    "iso-42001",
    "iso-27001",
    "soc2",
    "nist-800-92",
    ASI_FRAMEWORK,
)

STORE_REF = "docs/reference/store-format.md"
FORENSIC_REF = "docs/design/forensic-soundness.md"
IDENTITY_REF = "docs/design/agent-identity.md"
EVIDENCE_REF = "docs/reference/evidence-verifier.md"
COMPLIANCE_REF = "docs/reference/compliance.md"
OVERSIGHT_REF = "docs/design/authorization-provenance-v2.md"
ASI_REF = "docs/design/owasp-asi-mapping.md"
ASI_DOC_REF = "docs/compliance/owasp-asi-2026.md"


@dataclass(frozen=True)
class ControlResult:
    """One compliance row: control, evidence command, verdict, refs."""

    control: str
    title: str
    evidence: str
    verdict: str
    detail: str
    refs: tuple[str, ...] = ()
    tier: str = ""
    cannot_evidence: str = ""
    section: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "control": self.control,
            "title": self.title,
            "evidence": self.evidence,
            "verdict": self.verdict,
            "detail": self.detail,
            "refs": list(self.refs),
            "tier": self.tier,
            "cannot_evidence": self.cannot_evidence,
            "section": self.section,
        }


@dataclass(frozen=True)
class RetentionStatus:
    """Retention configuration vs the oldest retained record."""

    retention_days: int | None
    oldest_record_days: int | None
    records: int
    status: str  # configured | overdue | unknown
    detail: str = ""
    holds: int = 0
    overrides: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "retention_days": self.retention_days,
            "oldest_record_days": self.oldest_record_days,
            "records": self.records,
            "status": self.status,
            "detail": self.detail,
            "holds": self.holds,
            "overrides": self.overrides,
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
    state = last_state(store)
    days = state.retention_days or config.store.retention_days
    if days and days > 0:
        label = f" (profile {state.retention_profile})" if state.retention_profile else ""
        return PASS, f"retention configured for {days} day(s){label}"
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
        if record.agent.principal or record.agent.workload_identity or record.agent.delegation_chain
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


def _oversight_measurement(
    store: RecordStore, config: AgentwatchConfig, records: list[AgentRecord]
) -> tuple[str, str]:
    report = build_oversight(store)
    if report.total_calls:
        return (
            PASS,
            f"{report.total_calls} call(s) carry an authorization source; "
            f"{report.destructive_total} cls1 destructive/network/credential-adjacent",
        )
    return UNKNOWN, "no agent tool calls recorded to measure oversight"


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
    _ControlSpec(
        "oversight-measurement",
        "Human oversight is measured (authorization source + decisions)",
        "agentwatch oversight",
        (OVERSIGHT_REF,),
        _oversight_measurement,
    ),
)


_CHECKS: dict[str, _ControlSpec] = {spec.control: spec for spec in _CONTROLS}


@dataclass(frozen=True)
class _CoverageRow:
    """One coverage-map row (ASI-1): evidence or "not evidenced", never a verdict."""

    control: str
    section: str
    title: str
    evidence: str
    cannot_evidence: str
    tier: str
    refs: tuple[str, ...] = (ASI_REF,)


# OWASP Top 10 for Agentic Applications 2026 (ASI01–ASI10) + Agentic Skills Top
# 10 (AST01–AST10). Rows cite a real regenerating command (verified in the
# executable-docs gate) or say "not evidenced" and name the owning dependency;
# nothing here claims prevention or certification. When a row's evidence needs a
# ticket not yet landed on this branch (29.APV-3, 29.A2A-1/2, 30.CAP-1/2,
# 30.SBX-1), the row says so — that is the honest answer, not fake evidence.
_ASI_ROWS: tuple[_CoverageRow, ...] = (
    _CoverageRow(
        "ASI01",
        ASI_SECTION,
        "Content-to-argument flow edges and injection-shape observations are recorded (a signal, "
        "not an "
        "enforcement verdict).",
        "agentwatch flow <session>",
        "it cannot determine intent or block a goal hijack.",
        "signal",
    ),
    _CoverageRow(
        "ASI02",
        ASI_SECTION,
        "Every tool call is recorded with its outcome and a change footprint.",
        "agentwatch impact <session>",
        "it cannot classify a call as misuse or enforce a tool policy.",
        "evidenced",
    ),
    _CoverageRow(
        "ASI03",
        ASI_SECTION,
        "Records carry an on-behalf-of/workload identity and delegation chain (IDN).",
        "agentwatch search --identity <handle>",
        "privilege and authorization correctness are not evidenced; requires 29.APV-3 oversight "
        "(not on this "
        "branch).",
        "signal",
    ),
    _CoverageRow(
        "ASI04",
        ASI_SECTION,
        "Agentic supply chain compromise is not evidenced — requires 30.CAP-1 capability inventory "
        "(skills, "
        "plugins, hooks, rules, MCP).",
        NO_EVIDENCE,
        "skills/plugins/hooks/rules provenance and drift are not inventoried yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "ASI05",
        ASI_SECTION,
        "Command/execution classes and the change footprint are recorded (a signal); "
        "sandbox-boundary events "
        "are pending 30.SBX-1.",
        "agentwatch impact <session>",
        "it cannot block execution or prove a sandbox was enforced.",
        "signal",
    ),
    _CoverageRow(
        "ASI06",
        ASI_SECTION,
        "Memory read/write/delete records are observable and filterable (DET-7).",
        "agentwatch search --memory",
        "poisoning and attribution are not determined; an out-of-band memory edit is a signal, not "
        "a verdict.",
        "signal",
    ),
    _CoverageRow(
        "ASI07",
        ASI_SECTION,
        "Insecure inter-agent communication is not evidenced — requires 29.A2A-1/2 inter-agent "
        "capture and "
        "trace correlation.",
        NO_EVIDENCE,
        "A2A and delegation message capture is not landed on this branch.",
        "not evidenced",
    ),
    _CoverageRow(
        "ASI08",
        ASI_SECTION,
        "The subagent fan-out and retry/cascade observations are recorded.",
        "agentwatch tree <session>",
        "it cannot prove a cascade's root cause or severity.",
        "signal",
    ),
    _CoverageRow(
        "ASI09",
        ASI_SECTION,
        "Human-agent trust exploitation is not evidenced — requires 29.APV-3 oversight (approval "
        "mix, "
        "bypass, latency).",
        NO_EVIDENCE,
        "per-call authorization mode and the approval mix are not reported yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "ASI10",
        ASI_SECTION,
        "Behavior-fingerprint grouping and drift observations are recorded (a signal).",
        "agentwatch sessions --group-by-behavior",
        "it cannot label an agent rogue; findings are signals for review.",
        "signal",
    ),
    _CoverageRow(
        "AST01",
        AST_SECTION,
        "Malicious skills are not evidenced — requires 30.CAP-1 capability inventory.",
        NO_EVIDENCE,
        "skill content, publisher, and hash are not inventoried yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST02",
        AST_SECTION,
        "Supply chain compromise is not evidenced — requires 30.CAP-1/30.CAP-2 capability "
        "inventory and drift.",
        NO_EVIDENCE,
        "skill/plugin provenance and drift are not recorded yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST03",
        AST_SECTION,
        "Over-privileged skills are not evidenced — requires 30.CAP-1 permission inventory.",
        NO_EVIDENCE,
        "declared skill permissions are not captured yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST04",
        AST_SECTION,
        "Insecure skill metadata is not evidenced — requires 30.CAP-1 metadata capture.",
        NO_EVIDENCE,
        "skill frontmatter/manifests are not parsed into the record yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST05",
        AST_SECTION,
        "Untrusted external instructions are not evidenced — requires 30.CAP-1 plus DET-6 "
        "injection signals.",
        NO_EVIDENCE,
        "externally referenced skill content is not tracked yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST06",
        AST_SECTION,
        "Weak isolation is not evidenced — requires 30.SBX-1 sandbox-boundary events.",
        NO_EVIDENCE,
        "sandbox enforcement is not observable in the record yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST07",
        AST_SECTION,
        "Update drift is not evidenced — requires 30.CAP-2 capability drift.",
        NO_EVIDENCE,
        "skill/plugin version and content drift are not recorded yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST08",
        AST_SECTION,
        "Poor scanning is not evidenced — agentwatch does not scan skills for malware.",
        NO_EVIDENCE,
        "agentwatch records activity; it is not a skill scanner or an anti-malware verdict.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST09",
        AST_SECTION,
        "Missing governance / shadow AI is not evidenced — requires 30.CAP-1 inventory and 29.ACC "
        "governance.",
        NO_EVIDENCE,
        "a central skill inventory and approval workflow are not reported yet.",
        "not evidenced",
    ),
    _CoverageRow(
        "AST10",
        AST_SECTION,
        "Cross-platform skill reuse is not evidenced — requires 30.CAP-1 cross-platform inventory.",
        NO_EVIDENCE,
        "per-platform skill manifests are not compared yet.",
        "not evidenced",
    ),
)


def _asi_controls() -> tuple[ControlResult, ...]:
    """Build the ASI + AST10 coverage rows (evidence or an explicit "not evidenced")."""
    controls: list[ControlResult] = []
    for row in _ASI_ROWS:
        if row.evidence == NO_EVIDENCE:
            verdict = NOT_EVIDENCED
            detail = f"{row.tier}: not evidenced on this branch."
        else:
            verdict = EVIDENCED
            detail = (
                f"{row.tier}: {row.evidence} regenerates this; coverage only, "
                f"not a control verdict."
            )
        controls.append(
            ControlResult(
                control=row.control,
                title=row.title,
                evidence=row.evidence,
                verdict=verdict,
                detail=detail,
                refs=row.refs,
                tier=row.tier,
                cannot_evidence=row.cannot_evidence,
                section=row.section,
            )
        )
    return tuple(controls)


# Framework templates (M26 CMP-2): (control id, title, check key, refs). The
# check key selects one of the generic computed checks above; the id/title are
# the framework's own vocabulary. Generic keeps the default catalog.
_TEMPLATES: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    "eu-ai-act-art12": (
        (
            "art12-1-automatic-logging",
            "Automatic recording of events over the system's lifetime (Art. 12(1))",
            "log-integrity",
            (STORE_REF, FORENSIC_REF),
        ),
        (
            "art12-2-retention",
            "Record retention for high-risk systems (Art. 12 + AAT §9)",
            "retention-configured",
            (STORE_REF,),
        ),
        (
            "art12-3-traceability",
            "Traceability of an action to the acting identity",
            "identity-attribution",
            (IDENTITY_REF,),
        ),
        ("art12-4-integrity", "Integrity of the recorded log", "checkpointing", (FORENSIC_REF,)),
    ),
    "eu-ai-act-art14": (
        (
            "art14-human-oversight",
            "Human oversight of the high-risk AI system (Art. 14; OWASP ASI09)",
            "oversight-measurement",
            (OVERSIGHT_REF,),
        ),
        (
            "art14-authorization-provenance",
            "Who/what authorized each action is recorded (Art. 14)",
            "log-integrity",
            (OVERSIGHT_REF, STORE_REF),
        ),
    ),
    "iso-42001": (
        ("aims-logging", "AI management system event logging", "log-integrity", (STORE_REF,)),
        (
            "aims-retention",
            "Retention of AI system records",
            "retention-configured",
            (STORE_REF,),
        ),
        (
            "aims-identity",
            "Accountability to the acting agent",
            "identity-attribution",
            (IDENTITY_REF,),
        ),
        ("aims-evidence", "Evidence production for audits", "evidence-bundle", (EVIDENCE_REF,)),
    ),
    "iso-27001": (
        (
            "a8-15-logging",
            "A.8.15 Logging — event logs recorded and protected",
            "log-integrity",
            (STORE_REF,),
        ),
        (
            "a8-24-storage",
            "A.8.24 Use of cryptography / storage protection",
            "redaction-default",
            (STORE_REF,),
        ),
        (
            "a5-33-evidence",
            "A.5.33 Protection of records / evidence",
            "evidence-bundle",
            (EVIDENCE_REF,),
        ),
    ),
    "soc2": (
        (
            "cc7-1-monitoring",
            "CC7.1 Detection of configuration changes and anomalies",
            "log-integrity",
            (STORE_REF,),
        ),
        (
            "cc6-1-access",
            "CC6.1 Logical access — content protection",
            "redaction-default",
            (STORE_REF,),
        ),
        ("cc7-2-coverage", "CC7.2 Monitoring completeness", "recording-coverage", (FORENSIC_REF,)),
    ),
    "nist-800-92": (
        (
            "log-management-integrity",
            "Log management — integrity of log records",
            "log-integrity",
            (STORE_REF, FORENSIC_REF),
        ),
        ("log-retention", "Log retention and disposal", "retention-configured", (STORE_REF,)),
        (
            "log-protection",
            "Log protection — controlled content",
            "redaction-default",
            (STORE_REF,),
        ),
        (
            "log-accountability",
            "Attribution to a non-human identity",
            "identity-attribution",
            (IDENTITY_REF,),
        ),
    ),
}


def _retention_status(
    store: RecordStore, records: list[AgentRecord], config: AgentwatchConfig, now: datetime
) -> RetentionStatus:
    days = config.store.retention_days
    oldest: int | None = None
    if records:
        oldest = max(0, int((now - min(r.started_at for r in records)).total_seconds() // 86400))
    active = len(active_holds(store))
    overrides = sum(1 for marker in hold_records(store) if marker.action == "purge-override")
    if not days or days <= 0:
        return RetentionStatus(
            days,
            oldest,
            len(records),
            UNKNOWN,
            "no retention window configured",
            holds=active,
            overrides=overrides,
        )
    hold_note = (
        f"; {active} active legal hold(s), {overrides} purge override(s)"
        if active or overrides
        else ""
    )
    if oldest is not None and oldest > days:
        return RetentionStatus(
            days,
            oldest,
            len(records),
            "overdue",
            f"oldest record is {oldest}d old but retention is {days}d{hold_note}",
            holds=active,
            overrides=overrides,
        )
    return RetentionStatus(
        days,
        oldest,
        len(records),
        "configured",
        f"within the retention window{hold_note}",
        holds=active,
        overrides=overrides,
    )


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
    if framework == ASI_FRAMEWORK:
        controls: tuple[ControlResult, ...] = _asi_controls()
    else:
        template = _TEMPLATES.get(framework)
        rows = (
            [(c.control, c.title, c.control, c.refs) for c in _CONTROLS]
            if template is None
            else list(template)
        )
        results: list[ControlResult] = []
        for control_id, title, check_key, refs in rows:
            spec = _CHECKS[check_key]
            verdict, detail = spec.check(store, cfg, records)
            results.append(
                ControlResult(
                    control=control_id,
                    title=title,
                    evidence=spec.evidence,
                    verdict=verdict,
                    detail=detail,
                    refs=refs,
                )
            )
        controls = tuple(results)
    signature = SignatureStatus(
        signed=False,
        detail=(
            "checkpoint signing is not enabled (opt-in); unsigned checkpoints verify integrity only"
        ),
    )
    return ComplianceReport(
        framework=framework,
        installation="this installation",
        generated_at=moment,
        controls=controls,
        retention=_retention_status(store, records, cfg, moment),
        signature=signature,
        statement=_STATEMENT,
    )


def render_report(report: ComplianceReport) -> str:
    """Render the report as short text (verdicts, evidence, refs)."""
    lines = [
        f"agentwatch compliance {report.framework} ({report.installation})",
        f"  generated: {report.generated_at.isoformat()}",
    ]
    section = ""
    for control in report.controls:
        if control.section and control.section != section:
            section = control.section
            lines.append(f"  == {section} ==")
        lines.append(f"  [{control.verdict.upper()}] {control.control}: {control.title}")
        if control.tier:
            lines.append(f"    tier: {control.tier}")
        lines.append(f"    evidence: {control.evidence}")
        lines.append(f"    {control.detail}")
        if control.cannot_evidence:
            lines.append(f"    cannot evidence: {control.cannot_evidence}")
    if report.retention is not None:
        lines.append(
            f"  retention: {report.retention.status} "
            f"(window={report.retention.retention_days}d, "
            f"oldest={report.retention.oldest_record_days}d, "
            f"holds={report.retention.holds}, overrides={report.retention.overrides})"
        )
    if report.signature is not None:
        signed = "signed" if report.signature.signed else "unsigned"
        lines.append(f"  checkpoints: {signed} — {report.signature.detail}")
    lines.append(f"  {report.statement}")
    return "\n".join(lines)


__all__ = [
    "ASI_FRAMEWORK",
    "ASI_SECTION",
    "AST_SECTION",
    "EVIDENCED",
    "FAIL",
    "FRAMEWORKS",
    "NOT_EVIDENCED",
    "PASS",
    "UNKNOWN",
    "ComplianceReport",
    "ControlResult",
    "RetentionStatus",
    "SignatureStatus",
    "build_report",
    "render_report",
]
