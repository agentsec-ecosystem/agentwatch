"""Authorization provenance v2 derivation (M29 APV-1, PRD 49).

The record stores **who or what** authorized each call as a versioned taxonomy
(``human-once`` / ``human-remembered`` / ``rule`` / ``classifier`` / ``hook`` /
``bypass`` / ``not-required`` / ``denied`` / ``unknown``). This module holds the
single published mapping from a harness's native decision source and from the
legacy S14 five-value ``approval`` field, plus the derivation order:

1. a native decision source (Claude Code native telemetry, authoritative) wins;
2. a ``bypassPermissions`` mode means nothing was checking → ``bypass`` unless a
   more specific source is present;
3. otherwise the S14 ``approval`` value maps with ``evidence=inferred``; an
   indeterminate case stays ``unknown`` — never inferred from ``outcome=ok``.

Published in ``docs/design/authorization-provenance-v2.md`` and
``docs/reference/record-format-spec.md``.
"""

from __future__ import annotations

from agentwatch.records import (
    Approval,
    Authorization,
    AuthorizationDeny,
    AuthorizationEvidence,
    AuthorizationSource,
    PermissionMode,
)

# Version of the published taxonomy + mapping.
AUTHORIZATION_TAXONOMY_VERSION = "authz-v2"

# Legacy S14 ``approval`` -> v2 source. Historical records keep their stored
# value; ``effective_authorization`` maps them at read time only.
LEGACY_APPROVAL_MAP: dict[str, str] = {
    "user": AuthorizationSource.HUMAN_ONCE.value,
    "auto": AuthorizationSource.RULE.value,
    "not-required": AuthorizationSource.NOT_REQUIRED.value,
    "denied": AuthorizationSource.DENIED.value,
    "unknown": AuthorizationSource.UNKNOWN.value,
}

# Claude Code native ``tool_decision.decision_source`` -> v2 source.
NATIVE_DECISION_SOURCE_MAP: dict[str, AuthorizationSource] = {
    "config": AuthorizationSource.RULE,
    "hook": AuthorizationSource.HOOK,
    "user_permanent": AuthorizationSource.HUMAN_REMEMBERED,
    "user_temporary": AuthorizationSource.HUMAN_ONCE,
    "reject": AuthorizationSource.DENIED,
    "classifier": AuthorizationSource.CLASSIFIER,
}


def authorization_from_decision_source(decision_source: str) -> Authorization | None:
    """Map a native ``decision_source`` to v2, or ``None`` when unrecognized.

    ``None`` (never ``unknown``) signals "the harness said something we do not
    know" so the caller can fall through to the next derivation step rather than
    persisting a guess.
    """
    source = NATIVE_DECISION_SOURCE_MAP.get(decision_source)
    if source is None:
        return None
    deny = AuthorizationDeny.HUMAN if source is AuthorizationSource.DENIED else None
    return Authorization(
        source=source, deny=deny, evidence=AuthorizationEvidence.HARNESS_NATIVE
    )


def _legacy_source(approval: Approval) -> Authorization:
    source = AuthorizationSource(LEGACY_APPROVAL_MAP[approval.value])
    return Authorization(
        source=source,
        deny=AuthorizationDeny.UNKNOWN if source is AuthorizationSource.DENIED else None,
        evidence=AuthorizationEvidence.INFERRED,
    )


def derive_authorization(
    *,
    approval: Approval,
    decision_source: str | None = None,
    permission_mode: PermissionMode | None = None,
) -> Authorization:
    """Derive the v2 authorization for a call (first match wins).

    Never guesses: with no native source and no bypass mode, the S14 value maps
    with ``evidence=inferred`` and an indeterminate value stays ``unknown``.
    """
    if decision_source is not None:
        mapped = authorization_from_decision_source(decision_source)
        if mapped is not None:
            return mapped
    if permission_mode is PermissionMode.BYPASS_PERMISSIONS:
        return Authorization(
            source=AuthorizationSource.BYPASS,
            evidence=AuthorizationEvidence.SESSION_MODE,
        )
    return _legacy_source(approval)


def permission_mode_from(raw: object) -> PermissionMode:
    """Parse a raw permission-mode string; unrecognized/absent → ``unknown``."""
    if isinstance(raw, str):
        try:
            return PermissionMode(raw)
        except ValueError:
            return PermissionMode.UNKNOWN
    return PermissionMode.UNKNOWN


__all__ = [
    "AUTHORIZATION_TAXONOMY_VERSION",
    "LEGACY_APPROVAL_MAP",
    "NATIVE_DECISION_SOURCE_MAP",
    "authorization_from_decision_source",
    "derive_authorization",
    "permission_mode_from",
]
