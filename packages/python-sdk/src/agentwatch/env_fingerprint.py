"""Content-free environment fingerprint + delta (M30 ENV-1, PRD 57).

After a regression the first question is *"what changed?"* and the causes are
mostly environmental: the model, the harness, the permission mode, the loaded
capabilities, the rules files, the MCP surface, the effective recorder config.
This module derives a **content-free** fingerprint per session from what the
record already holds — names, versions and digests only, absent facts ``unknown``
— so ``diff`` can print an environment delta beside the behavior delta and
``drift`` can annotate a shift with environment changes in the same window.

The wording is "coincides with", never "caused by": a fingerprint is an
observation, not a causal claim.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from agentwatch.capabilities import (
    CAP_KIND_RULES,
    Capability,
    survey_capabilities,
)
from agentwatch.mcp_surface import survey
from agentwatch.recorder_state import RECORDER_ATTESTED_TOOL
from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

ENV_DIGEST_VERSION = "env1"
UNKNOWN = "unknown"

# Priority order: the model surfaces first (the seed of most regressions).
ENV_FIELDS: tuple[str, ...] = (
    "model",
    "harness",
    "permission_mode",
    "capabilities",
    "rules",
    "mcp_surface",
    "config",
)


def _combine(items: Sequence[str]) -> str:
    """A stable digest of a set of strings, or ``unknown`` when empty."""
    if not items:
        return UNKNOWN
    payload = "\n".join(sorted(set(items))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class EnvironmentFingerprint:
    """One session's content-free environment, component by component."""

    model: str = UNKNOWN
    harness: str = UNKNOWN
    permission_mode: str = UNKNOWN
    capabilities: str = UNKNOWN
    rules: str = UNKNOWN
    mcp_surface: str = UNKNOWN
    config: str = UNKNOWN

    def components(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in ENV_FIELDS}

    def digest(self) -> str:
        canonical = json.dumps(self.components(), sort_keys=True).encode("utf-8")
        return f"{ENV_DIGEST_VERSION}:{hashlib.sha256(canonical).hexdigest()}"

    def to_dict(self) -> dict[str, str]:
        return {**self.components(), "digest": self.digest()}


@dataclass(frozen=True)
class EnvironmentChange:
    """A single changed fingerprint component between two environments."""

    field: str
    a: str
    b: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "a": self.a, "b": self.b}


@dataclass(frozen=True)
class DatedEnvironmentChange:
    """An environment change stamped with the session time it first appeared."""

    at: datetime
    change: EnvironmentChange


@dataclass(frozen=True)
class SessionEnvironment:
    """A session's fingerprint and its first-seen time."""

    session_id: str
    at: datetime
    fingerprint: EnvironmentFingerprint


def _capabilities_from(records: Sequence[AgentRecord]) -> tuple[list[Capability], list[Capability]]:
    all_caps: list[Capability] = []
    rule_caps: list[Capability] = []
    for state in survey_capabilities(records):
        for capability in state.capabilities:
            all_caps.append(capability)
            if capability.kind == CAP_KIND_RULES:
                rule_caps.append(capability)
    return all_caps, rule_caps


def environment_fingerprint(records: Sequence[AgentRecord]) -> EnvironmentFingerprint:
    """Derive a content-free environment fingerprint from a record sequence."""
    model = UNKNOWN
    harness = UNKNOWN
    permission_mode = UNKNOWN
    config = UNKNOWN
    for record in records:
        if record.agent.model_version:
            model = record.agent.model_version
        if record.harness:
            harness = record.harness
        if record.permission_mode is not None:
            permission_mode = record.permission_mode.value
        if record.tool.name == RECORDER_ATTESTED_TOOL:
            arguments = record.tool.arguments or {}
            stored = arguments.get("config_digest")
            if isinstance(stored, str) and stored:
                config = stored

    all_caps, rule_caps = _capabilities_from(records)
    capability_digest = _combine(
        [f"{cap.kind}:{cap.scope}:{cap.name}:{cap.digest}" for cap in all_caps]
    )
    rules_digest = _combine([f"{cap.scope}:{cap.name}:{cap.digest}" for cap in rule_caps])
    mcp_digest = _combine([f"{state.server}:{state.digest}" for state in survey(records)])

    return EnvironmentFingerprint(
        model=model,
        harness=harness,
        permission_mode=permission_mode,
        capabilities=capability_digest,
        rules=rules_digest,
        mcp_surface=mcp_digest,
        config=config,
    )


def environment_delta(
    a: EnvironmentFingerprint, b: EnvironmentFingerprint
) -> list[EnvironmentChange]:
    """The changed components, in the fixed priority order (model first)."""
    changes: list[EnvironmentChange] = []
    for field in ENV_FIELDS:
        before = getattr(a, field)
        after = getattr(b, field)
        if before != after:
            changes.append(EnvironmentChange(field=field, a=before, b=after))
    return changes


def _group_records(records: Iterable[AgentRecord]) -> dict[str, list[AgentRecord]]:
    by_session: dict[str, list[AgentRecord]] = {}
    for record in records:
        by_session.setdefault(record.session_id, []).append(record)
    return by_session


def session_environments(store: RecordStore) -> list[SessionEnvironment]:
    """Every session's environment fingerprint, ordered by first-seen time."""
    environments: list[SessionEnvironment] = []
    for session_id, records in _group_records(store.records()).items():
        at = min(record.started_at for record in records)
        environments.append(
            SessionEnvironment(
                session_id=session_id,
                at=at,
                fingerprint=environment_fingerprint(records),
            )
        )
    return sorted(environments, key=lambda env: (env.at, env.session_id))


def environment_changes(
    environments: Sequence[SessionEnvironment],
) -> list[DatedEnvironmentChange]:
    """Consecutive-session environment changes, stamped with the later time."""
    dated: list[DatedEnvironmentChange] = []
    for prev, current in zip(environments, environments[1:], strict=False):
        if prev.fingerprint.digest() == current.fingerprint.digest():
            continue
        for change in environment_delta(prev.fingerprint, current.fingerprint):
            dated.append(DatedEnvironmentChange(at=current.at, change=change))
    return dated


def annotate_environment(
    *,
    signal_at: datetime,
    changes: Sequence[DatedEnvironmentChange],
    window_seconds: float,
) -> list[EnvironmentChange]:
    """Environment changes within ``window_seconds`` before ``signal_at``.

    These *coincide with* the signal; the caller must not present them as a cause.
    """
    annotated: list[EnvironmentChange] = []
    for dated in changes:
        delta = (signal_at - dated.at).total_seconds()
        if 0.0 <= delta <= window_seconds:
            annotated.append(dated.change)
    return annotated


def group_sessions_by_env(store: RecordStore) -> dict[str, tuple[str, ...]]:
    """Group every session by its environment fingerprint, first-seen order."""
    groups: dict[str, list[str]] = {}
    for environment in session_environments(store):
        groups.setdefault(environment.fingerprint.digest(), []).append(environment.session_id)
    return {digest: tuple(sessions) for digest, sessions in groups.items()}


def render_env_groups(groups: dict[str, tuple[str, ...]]) -> str:
    """Render environment groups as ``ENV  SESSIONS  COUNT`` lines."""
    lines = ["ENV\tSESSIONS\tCOUNT"]
    for digest, sessions in groups.items():
        lines.append(f"{digest}\t{','.join(sessions)}\t{len(sessions)}")
    return "\n".join(lines)


def render_environment_delta(changes: Sequence[EnvironmentChange]) -> str:
    if not changes:
        return "environment: unchanged"
    lines = ["environment:"]
    for change in changes:
        lines.append(f"  {change.field}: {change.a} -> {change.b}")
    return "\n".join(lines)


__all__ = [
    "ENV_DIGEST_VERSION",
    "ENV_FIELDS",
    "UNKNOWN",
    "DatedEnvironmentChange",
    "EnvironmentChange",
    "EnvironmentFingerprint",
    "SessionEnvironment",
    "annotate_environment",
    "environment_changes",
    "environment_delta",
    "environment_fingerprint",
    "group_sessions_by_env",
    "render_env_groups",
    "render_environment_delta",
    "session_environments",
]
