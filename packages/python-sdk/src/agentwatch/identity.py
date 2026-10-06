"""Agent-identity privacy policy (M25 IDN-1, PRD 44).

The ``agent_identity`` dimension (record schema 0.2.0) answers *which non-human
entity, under which credential, on whose behalf*. Two hard rules:

* **No secret material** ever reaches an identity field — every identity string
  runs through the secrets pipeline before it is recorded.
* **On-behalf-of principals are hashed by default.** Plaintext ``principal`` /
  ``delegation_chain`` requires the explicit ``full`` privacy mode (operator
  consent), mirroring DD-06. ``credential_class`` is a classification, never a
  credential value.

Hashing is a stable, per-install keyed HMAC-SHA256 (the same keyed mechanism as
content-flow fingerprints): the same principal is correlatable within one
installation but not recoverable from the store, and not enumerable across
installations.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace

from agentwatch.records import AgentIdentity, RecordPrivacyMode
from agentwatch.secrets import SECRET_KINDS, detect

IDENTITY_HASH_PREFIX = "hmac-sha256:"
# Fail-closed fallback used only when no per-install key exists yet: weaker than
# the keyed HMAC against enumeration, but it still never emits plaintext.
_FALLBACK_SALT = "agentwatch.identity.v1:"

# The hard rule is "identity fields never contain *secret material*". PII classes
# (an email principal, a phone) are the dimension's legitimate subject and are
# hashed by the principal policy rather than masked here; masking them would make
# an identity dimension useless.
_PII_KINDS = frozenset({"email", "phone", "ssn", "credit-card"})
_SECRET_MATERIAL_KINDS = tuple(
    kind for kind in SECRET_KINDS if kind not in _PII_KINDS and kind != "env-secret"
)
_SECRET_MATERIAL_SET = frozenset(_SECRET_MATERIAL_KINDS)


def _mask_secret_material(text: str) -> tuple[str, tuple[str, ...]]:
    """Mask only secret-material spans (never PII) in ``text``."""
    matches = [match for match in detect(text) if match.kind in _SECRET_MATERIAL_SET]
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
    kinds = tuple(kind for kind in _SECRET_MATERIAL_KINDS if kind in found)
    return "".join(parts), kinds


def _per_install_key() -> bytes | None:
    from agentwatch import flow

    return flow.hmac_key_or_none()


def hash_principal(value: str, *, key: bytes | None = None) -> str:
    """A stable, non-reversible handle for a principal.

    Keyed with the per-install HMAC key when available so the same principal is
    correlatable within an installation but not recoverable (and not comparable
    across installations). Never returns the input; empty input yields ``""``.
    """
    text = value.strip()
    if not text:
        return ""
    resolved = key if key is not None else _per_install_key()
    if resolved:
        digest = hmac.new(resolved, text.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    else:
        digest = hashlib.sha256((_FALLBACK_SALT + text).encode("utf-8")).hexdigest()[:16]
    return IDENTITY_HASH_PREFIX + digest


def scrub_identity(agent: AgentIdentity) -> AgentIdentity:
    """Return a copy with secret material masked in every identity string field.

    A defensive second pass behind the capture-time redaction: even an explicit
    ``full`` privacy mode must never persist a secret inside an identity field.
    """
    masked = replace(
        agent,
        identity=_mask(agent.identity),
        name=_mask_opt(agent.name),
        version=_mask_opt(agent.version),
        prompt_version=_mask_opt(agent.prompt_version),
        model_version=_mask_opt(agent.model_version),
        tool_schema_version=_mask_opt(agent.tool_schema_version),
        workload_type=_mask_opt(agent.workload_type),
        workload_identity=_mask_opt(agent.workload_identity),
        principal=_mask_opt(agent.principal),
        delegation_chain=(
            tuple(_mask(entry) for entry in agent.delegation_chain)
            if agent.delegation_chain is not None
            else None
        ),
    )
    return masked


def apply_identity_privacy(
    agent: AgentIdentity,
    *,
    mode: RecordPrivacyMode = RecordPrivacyMode.METADATA_ONLY,
    key: bytes | None = None,
) -> AgentIdentity:
    """Apply the principal-hashing policy and secret-safety scrub.

    Under every mode except ``full`` the ``principal`` and each
    ``delegation_chain`` entry are replaced by a keyed handle; under ``full``
    (operator consent) the plaintext is kept — but secrets are still masked.
    """
    scrubbed = scrub_identity(agent)
    if mode is RecordPrivacyMode.FULL:
        return scrubbed
    principal = scrubbed.principal
    chain = scrubbed.delegation_chain
    return replace(
        scrubbed,
        principal=hash_principal(principal, key=key) if principal else None,
        delegation_chain=(
            tuple(hash_principal(entry, key=key) for entry in chain) if chain else None
        ),
    )


def identity_handles(agent: AgentIdentity) -> tuple[str, ...]:
    """Every identity handle on an agent (for `search --identity`).

    Includes the agent identity/name, the on-behalf-of principal, the workload
    identity, and each delegation-chain entry — absent fields are omitted, never
    synthesized.
    """
    values = [agent.identity, agent.name, agent.principal, agent.workload_identity]
    if agent.delegation_chain is not None:
        values.extend(agent.delegation_chain)
    return tuple(value for value in values if isinstance(value, str) and value)


def identity_secret_kinds(agent: AgentIdentity) -> tuple[str, ...]:
    """The secret classes present in any identity field (for the guard/property test)."""
    kinds: list[str] = []
    for value in _identity_strings(agent):
        kinds.extend(_mask_secret_material(value)[1])
    return tuple(dict.fromkeys(kinds))


def _mask(value: str) -> str:
    return _mask_secret_material(value)[0]


def _mask_opt(value: str | None) -> str | None:
    return _mask(value) if isinstance(value, str) else value


def _identity_strings(agent: AgentIdentity) -> list[str]:
    values = [
        agent.identity,
        agent.name,
        agent.version,
        agent.prompt_version,
        agent.model_version,
        agent.tool_schema_version,
        agent.workload_type,
        agent.workload_identity,
        agent.principal,
    ]
    if agent.delegation_chain is not None:
        values.extend(agent.delegation_chain)
    return [value for value in values if isinstance(value, str)]


__all__ = [
    "IDENTITY_HASH_PREFIX",
    "apply_identity_privacy",
    "hash_principal",
    "identity_handles",
    "identity_secret_kinds",
    "scrub_identity",
]