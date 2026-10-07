"""Anomaly detection package — exports all 35 detectors and a factory function.

The detectors are organized by domain:

- **Tool execution** (``tool.py``): 8 detectors for tool call patterns, errors,
  latency, timeouts, and redundancy.
- **Cost & resource** (``cost.py``): 6 detectors for cost spikes, efficiency,
  token explosions, and wasted calls.
- **Runtime & completion** (``runtime.py``): 5 detectors for run duration,
  step budgets, inactivity, and premature completion.
- **Retry & recovery** (``retry.py``): 5 detectors for retry storms, systemic
  failures, transient storms, cascading retries, and recovery paths.
- **Interaction & control** (``interaction.py``): 4 detectors for human
  interventions, escalations, approval latency, and rejections.
- **Output quality** (``output.py``): 4 detectors for empty/low output,
  indeterminate status, and output drift.
- **Cross-run patterns** (``cross_run.py``): 3 detectors for anomaly
  clustering, run frequency anomalies, and first-run heuristics.

**Factory usage**::

    from analytics.detectors import create_all_detectors
    detectors = create_all_detectors()

All detectors inherit from ``BaseDetector`` and expose a ``detect(summary, spans)``
method (optionally async via ``detect_async``).
"""

from __future__ import annotations

from analytics.detectors.base import BaseDetector
from analytics.detectors.claude_code import (
    DeniedClusterDetector,
    NetworkToolDetector,
    WriteStormDetector,
)
from analytics.detectors.cost import (
    CostEfficiencyDetector,
    CostSpikeDetector,
    CostVsBaselineDetector,
    PerToolCostSpikeDetector,
    TokenExplosionDetector,
    WastedToolCallsDetector,
)
from analytics.detectors.cross_run import (
    AnomalyClusterDetector,
    FirstRunHeuristicDetector,
    RunFrequencyAnomalyDetector,
)
from analytics.detectors.identity import CredentialHygieneDetector
from analytics.detectors.injection import InjectionShapeDetector
from analytics.detectors.interaction import (
    ApprovalLatencyDetector,
    EscalationRateDetector,
    InterventionFrequencyDetector,
    InterventionRejectionDetector,
)
from analytics.detectors.llm import (
    ConfusionPatternDetector,
    EmbeddingDriftDetector,
    GoalDriftDetector,
    HallucinationDetector,
    QualityDegradationDetector,
    SemanticLoopDetector,
)
from analytics.detectors.output import (
    EmptyResponseDetector,
    IndeterminateDetector,
    LowOutputDetector,
    OutputDriftDetector,
)
from analytics.detectors.retry import (
    CascadingRetryDetector,
    RecoveryPathDetector,
    RetryStormDetector,
    SystemicRetryDetector,
    TransientRetryDetector,
)
from analytics.detectors.runtime import (
    InactivityDetector,
    MaxStepHitDetector,
    PrematureCompletionDetector,
    RunDurationDetector,
    StepEfficiencyDetector,
)
from analytics.detectors.tool import (
    ArgumentLoopDetector,
    LoopDetector,
    PatternLoopDetector,
    RedundantToolCallDetector,
    SpecificToolErrorDetector,
    ToolErrorRateDetector,
    ToolLatencyDetector,
    ToolTimeoutDetector,
)
from analytics.llm_client import LLMClient


def create_all_detectors() -> list[BaseDetector]:
    """Factory: instantiate all 35 detectors with default thresholds from settings.

    Each detector reads its thresholds from ``settings.*`` environment
    variables.  Detectors are instantiated without arguments so they pick
    up the current configuration.

    Returns:
        A list of 35 detector instances, ordered by category.
    """
    return [
        # Tool execution (8)
        LoopDetector(),
        PatternLoopDetector(),
        ArgumentLoopDetector(),
        ToolErrorRateDetector(),
        SpecificToolErrorDetector(),
        ToolLatencyDetector(),
        ToolTimeoutDetector(),
        RedundantToolCallDetector(),
        # Cost & resource (6)
        CostSpikeDetector(),
        CostVsBaselineDetector(),
        CostEfficiencyDetector(),
        TokenExplosionDetector(),
        PerToolCostSpikeDetector(),
        WastedToolCallsDetector(),
        # Runtime & completion (5)
        RunDurationDetector(),
        MaxStepHitDetector(),
        StepEfficiencyDetector(),
        InactivityDetector(),
        PrematureCompletionDetector(),
        # Retry & recovery (5)
        RetryStormDetector(),
        SystemicRetryDetector(),
        TransientRetryDetector(),
        CascadingRetryDetector(),
        RecoveryPathDetector(),
        # Interaction & control (4)
        InterventionFrequencyDetector(),
        EscalationRateDetector(),
        ApprovalLatencyDetector(),
        InterventionRejectionDetector(),
        # Output quality (4)
        EmptyResponseDetector(),
        LowOutputDetector(),
        IndeterminateDetector(),
        OutputDriftDetector(),
        # Cross-run patterns (3)
        AnomalyClusterDetector(),
        RunFrequencyAnomalyDetector(),
        FirstRunHeuristicDetector(),
        # Claude Code hook records (3, M6 addition L1)
        WriteStormDetector(),
        DeniedClusterDetector(),
        NetworkToolDetector(),
        # Identity / credential hygiene (1, M28 IDN-4)
        CredentialHygieneDetector(),
        # Injection-shaped content (1, M28 DET-6)
        InjectionShapeDetector(),
    ]


def create_llm_detectors(client: LLMClient) -> list[BaseDetector]:
    """Factory: the 6 LLM-augmented detectors bound to a local-first client (DET-4).

    Kept separate from :func:`create_all_detectors` so the deterministic rule-based
    trust path never depends on a model: the LLM layer is strictly additive and
    degrades to no-op when the local endpoint is unavailable.
    """
    return [
        EmbeddingDriftDetector(client),
        SemanticLoopDetector(client),
        HallucinationDetector(client),
        GoalDriftDetector(client),
        QualityDegradationDetector(client),
        ConfusionPatternDetector(client),
    ]


__all__ = [
    "BaseDetector",
    "LoopDetector",
    "PatternLoopDetector",
    "ArgumentLoopDetector",
    "ToolErrorRateDetector",
    "SpecificToolErrorDetector",
    "ToolLatencyDetector",
    "ToolTimeoutDetector",
    "RedundantToolCallDetector",
    "CostSpikeDetector",
    "CostVsBaselineDetector",
    "CostEfficiencyDetector",
    "TokenExplosionDetector",
    "PerToolCostSpikeDetector",
    "WastedToolCallsDetector",
    "RunDurationDetector",
    "MaxStepHitDetector",
    "StepEfficiencyDetector",
    "InactivityDetector",
    "PrematureCompletionDetector",
    "RetryStormDetector",
    "SystemicRetryDetector",
    "TransientRetryDetector",
    "CascadingRetryDetector",
    "RecoveryPathDetector",
    "InterventionFrequencyDetector",
    "EscalationRateDetector",
    "ApprovalLatencyDetector",
    "InterventionRejectionDetector",
    "EmptyResponseDetector",
    "LowOutputDetector",
    "IndeterminateDetector",
    "OutputDriftDetector",
    "AnomalyClusterDetector",
    "RunFrequencyAnomalyDetector",
    "FirstRunHeuristicDetector",
    "WriteStormDetector",
    "DeniedClusterDetector",
    "NetworkToolDetector",
    "CredentialHygieneDetector",
    "InjectionShapeDetector",
    "create_all_detectors",
    "create_llm_detectors",
]
