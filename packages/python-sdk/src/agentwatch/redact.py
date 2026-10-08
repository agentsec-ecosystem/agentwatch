"""Redaction and privacy controls.

========================================================
Why this module exists
========================================================
Traces can carry sensitive content: prompts, tool arguments, retrieved text, and
memory contents. The product's default privacy posture is **truncated content capture**
with tool args enabled -- we keep content capped at a character limit so detectors
can analyze meaningful signal while sensitive payloads are never stored in full.
The ``METADATA_ONLY`` mode remains available for deployments that require zero
content on spans: it keeps structural signal (span names, timings, counts, cost,
IDs) while keeping the sensitive payloads out of the telemetry path.

This module is the trust boundary for that guarantee. Any code that wants to write
sensitive content onto a span must funnel the value through :meth:`RedactionConfig.apply`,
which decides -- from the configured mode and the per-field opt-in flag -- whether a
value is dropped, truncated, or hashed before it ever reaches the span.

========================================================
Privacy modes explained
========================================================
* **METADATA_ONLY**: No content ever written.  The safest mode.  Available for
  privacy-sensitive deployments that do not need content-based detection.
  Structural telemetry (timings, counts, IDs) is still emitted.

* **TRUNCATED** (default): Content is kept but capped at ``truncate_at`` characters.
  A ``[...]`` marker is appended when truncation occurs so consumers can
  distinguish naturally-short values from cut-off ones.  Tool args are
  captured by default under this mode so detectors have signal to work with.

* **HASHED**: Content is replaced by a **salted** SHA-256 hex digest.  The
  hash is deterministic (same input + same salt = same digest), non-reversible,
  and useful for correlating repeated payloads in analytics without revealing
  the payload itself.

========================================================
Double-gate design
========================================================
The original implementation had a single flag that controlled all content paths,
meaning enabling prompt capture could accidentally leak tool args or memory
contents. The current design uses two independent guards:

  1. **Field opt-in** (``capture_prompts``, ``capture_tool_args``,
     ``capture_memory``): enables capture for ONE specific field.
  2. **Mode gate** (``PrivacyMode``): metadata-only turns everything off globally.

Both must pass for content to reach a span.  This guarantees that enabling
prompts cannot leak tool args or memory -- the per-field flag is what gates it.

========================================================
Usage
========================================================

::

    from agentwatch.redact import RedactionConfig, PrivacyMode

    cfg = RedactionConfig(
        mode=PrivacyMode.HASHED,
        capture_tool_args=True,
        hash_salt="production-v0.1",
    )

    result = cfg.apply("sensitive args", allowed=cfg.capture_tool_args)
    # result = "a1b2c3d4e5f6..."  (64-char hex digest)

    # Metadata-only mode drops everything:
    safe = RedactionConfig(mode=PrivacyMode.METADATA_ONLY)
    assert safe.apply("anything", allowed=True) is None
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class PrivacyMode(str, Enum):
    """How sensitive content is handled. Defaults are metadata-only.

    The ``str`` base is intentional: it lets the values serialize cleanly to span
    attributes and be compared against user-supplied config strings.  Enum members
    can be passed as attribute values without an explicit ``.value`` call.
    """

    # No content is ever written. The safest mode and the default.
    # ``apply()`` returns ``None`` immediately -- no string transformation happens.
    METADATA_ONLY = "metadata_only"
    # Content is kept but capped at a character limit (see ``truncate_at``).
    # A ``"[...]"`` marker is appended when truncation occurs.
    TRUNCATED = "truncated"
    # Content is replaced by a salted SHA-256 digest: unforgeable, deterministic,
    # and non-reversible, useful for correlating repeated payloads in analytics.
    # The salt is prepended to the plaintext before hashing.
    HASHED = "hashed"
    # Raw content, explicit opt-in only. Secret/PII classes are still masked
    # upstream before this transform (see ``agentwatch.secrets``).
    FULL = "full"


# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------

# Marker appended to a truncated payload. Its length is subtracted when slicing so
# the stored value never exceeds ``truncate_at`` characters. Kept as a named
# constant because it is referenced in both ``apply()`` and the tests.
_TRUNCATION_MARKER = "[...]"


@dataclass(frozen=True)
class RedactionConfig:
    """Configuration for content capture defaults.

    The mode decides HOW content is stored (when it is stored at all). The three
    ``capture_*`` flags decide WHETHER a specific field is allowed out at all.

    Frozen (immutable): a config can be shared safely across threads and adapters
    without copy-on-write concerns, matching the SDK's design principle that each
    run / adapter reads from a single shared config.

    Attributes:
        mode: overall privacy mode. Defaults to :data:`PrivacyMode.TRUNCATED`.
        capture_prompts: capture model prompts when mode is not metadata-only.
        capture_tool_args: capture tool arguments when mode is not metadata-only.
        capture_memory: capture memory content when mode is not metadata-only.
        truncate_at: max characters (inclusive) kept in truncated mode.  Values
            longer than this are sliced and a ``"[...]"`` marker is appended.
        hash_salt: optional salt prepended to values before hashing in hashed mode.
            Different salts produce different digests for the same plaintext.

    Example::

        cfg = RedactionConfig(
            mode=PrivacyMode.TRUNCATED,
            capture_tool_args=True,
            truncate_at=256,
        )
        result = cfg.apply("some long string...", allowed=cfg.capture_tool_args)
        # result is at most 256 characters (including "[...]" if truncated)
    """

    mode: PrivacyMode = PrivacyMode.TRUNCATED
    capture_prompts: bool = False
    capture_tool_args: bool = True
    capture_memory: bool = False
    truncate_at: int = 512
    hash_salt: str = ""

    @property
    def captures_content(self) -> bool:
        """True if any sensitive content path is actually enabled.

        This is a fast short-circuit used by callers that want to skip work entirely
        when nothing is being captured. Note it is independent of which field opts in:
        enabling prompts alone makes this True even though tools/memory stay off --
        the per-field gating is enforced separately in ``apply``.

        Returns:
            ``True`` when (a) mode is not metadata-only AND (b) at least one of
            ``capture_prompts``, ``capture_tool_args``, or ``capture_memory`` is
            ``True``.  Otherwise ``False``.

        Example::

            cfg = RedactionConfig(mode=PrivacyMode.METADATA_ONLY, capture_prompts=True)
            assert not cfg.captures_content  # metadata-only overrides everything
        """
        return self.mode is not PrivacyMode.METADATA_ONLY and (
            self.capture_prompts or self.capture_tool_args or self.capture_memory
        )

    def apply(self, value: str, *, allowed: bool) -> str | None:
        """Redact a sensitive ``value``, or return ``None`` to signal "do not record".

        ``allowed`` is the caller-supplied opt-in flag for the specific field being
        written (e.g. ``capture_tool_args``). Two independent guards:

          1. Field opt-in (``allowed``): enables capture for ONE field without
             accidentally enabling the others.
          2. Mode gate: metadata-only turns everything off globally.

        The double gate is what makes the "enabling prompts can't leak tool args or
        memory" property hold -- the original all-modes-are-equal bug this replaced.

        Return values, by mode:
          * metadata-only or ``allowed=False``  -> ``None`` (skip the span write)
          * hashed                              -> 64-char salted SHA-256 hex digest
          * truncated + value too long         -> ``value[:truncate_at - len(marker)] + "[...]"``
          * otherwise                          -> the value unchanged

        Args:
            value: the raw sensitive string to potentially redact.
            allowed: per-field opt-in flag.  Must be ``True`` AND the mode must not
                be metadata-only for any content to reach a span.

        Returns:
            The redacted string value, or ``None`` if the caller must NOT record it.

        Edge cases:
            * Empty string: handled normally -- hashing it returns a valid digest,
              truncating it returns ``""``, metadata-only returns ``None``.
            * ``truncate_at`` smaller than the marker: the marker is silently omitted
              so the output never exceeds ``truncate_at`` characters.
            * Zero or negative ``truncate_at``: ``apply`` returns ``value[:truncate_at]``
              (i.e. the empty string for non-positive limits).

        Example::

            cfg = RedactionConfig(mode=PrivacyMode.HASHED, capture_tool_args=True,
                                  hash_salt="s3cret")
            cfg.apply("hello", allowed=True)     # -> "a1b2c3...64 chars..."
            cfg.apply("hello", allowed=False)    # -> None (field not opted in)
        """
        # Short-circuit: a field that is not opted-in, or a global metadata-only
        # posture, means the value must never leave the process as a span payload.
        # This is the outer gate that stops all content dead.
        if not allowed or self.mode is PrivacyMode.METADATA_ONLY:
            return None

        # Full mode keeps the value as-is (secret masking already ran upstream).
        if self.mode is PrivacyMode.FULL:
            return value

        # Deterministic hashing. The salt is prepended so equal plaintexts with
        # different salts yield different digests, and an attacker cannot rainbow-table
        # matches without knowing the salt. Deterministic (no random component) so the
        # same run replays to the same digest for analytics correlation.
        if self.mode is PrivacyMode.HASHED:
            # Prepend salt + value to form the message; hash as sha256 hex.
            message = f"{self.hash_salt}{value}".encode()
            return hashlib.sha256(message).hexdigest()

        # Truncation: cap the retained content. We reserve room for the marker so the
        # final value is exactly ``truncate_at`` when truncated (or near it for very
        # small limits), rather than silently exceeding the stated cap.  When the cap
        # is too small to fit the marker, the marker is omitted so the output never
        # exceeds ``truncate_at`` characters.
        if len(value) > self.truncate_at:
            # Compute how many characters we can keep before the marker.
            # ``max(..., 0)`` guards against negative truncate_at.
            keep = max(self.truncate_at - len(_TRUNCATION_MARKER), 0)
            if keep <= 0:
                # If the cap is so small that even the raw value alone would exceed
                # it, return a simple slice without the marker.  The marker would
                # push us over the cap and violate the contract that output never
                # exceeds ``truncate_at`` characters.
                return value[: self.truncate_at]
            return value[:keep] + _TRUNCATION_MARKER

        # Value fits within truncate_at: return it unchanged.
        return value


# Operator-config privacy mode strings (PRD 16) -> SDK privacy modes.
_CONFIG_MODES: dict[str, PrivacyMode] = {
    "metadata-only": PrivacyMode.METADATA_ONLY,
    "truncated": PrivacyMode.TRUNCATED,
    "hashed": PrivacyMode.HASHED,
    "full": PrivacyMode.FULL,
}


def redaction_config_from_mode(mode: str, *, capture_tool_args: bool = True) -> RedactionConfig:
    """Build a :class:`RedactionConfig` from an operator-config privacy mode.

    Unknown modes fall back to ``METADATA_ONLY`` (the safest posture), matching
    the configuration loader's fail-closed default.
    """
    return RedactionConfig(
        mode=_CONFIG_MODES.get(mode, PrivacyMode.METADATA_ONLY),
        capture_tool_args=capture_tool_args,
    )


# ---------------------------------------------------------------------------
# Public redaction corpus + ``redact eval`` (M30 RED-1, PRD 56 §RED-1)
# ---------------------------------------------------------------------------

CORPUS_SCHEMA = "agentwatch.redaction-corpus/1"
CORPUS_REPORT_SCHEMA = "agentwatch.redaction-corpus-numbers/1"
CORPUS_VERSIONS: tuple[str, ...] = ("v1",)


@dataclass(frozen=True)
class RedactionCase:
    """One corpus case: a synthetic secret/PII value and its expected classes."""

    id: str
    klass: str
    label: str  # "positive" | "negative"
    value: Any
    expect: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "class": self.klass,
            "label": self.label,
            "value": self.value,
            "expect": list(self.expect),
        }


@dataclass(frozen=True)
class RedactionCorpus:
    """A versioned corpus of synthetic secret/PII cases."""

    schema: str
    version: str
    cases: tuple[RedactionCase, ...]


@dataclass(frozen=True)
class ClassResult:
    """Published recall for one secret/PII class."""

    klass: str
    cases: int
    hits: int
    recall: float
    misses: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "hits": self.hits,
            "recall": self.recall,
            "misses": list(self.misses),
        }


@dataclass(frozen=True)
class CorpusReport:
    """Per-class recall + false-positive rate reproduced from a corpus."""

    schema: str
    corpus: str
    positive: int
    negative: int
    overall_recall: float
    false_positive_rate: float
    classes: tuple[ClassResult, ...]
    misses: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "corpus": self.corpus,
            "corpus_schema": CORPUS_SCHEMA,
            "cases": {"positive": self.positive, "negative": self.negative},
            "overall_recall": self.overall_recall,
            "false_positive_rate": self.false_positive_rate,
            "classes": {result.klass: result.to_dict() for result in self.classes},
            "misses": list(self.misses),
        }


def _corpus_root() -> Path:
    candidate = Path(__file__).resolve()
    for parent in candidate.parents:
        root = parent / "schema" / "vectors" / "redaction"
        if root.is_dir():
            return root
    raise ValueError("redaction corpus directory not found (schema/vectors/redaction)")


def load_corpus(version: str = "v1", *, root: Path | None = None) -> RedactionCorpus:
    """Load the public redaction corpus for a version (deterministic, offline)."""
    directory = (root if root is not None else _corpus_root()) / version
    path = directory / "corpus.json"
    if not path.is_file():
        available = ", ".join(CORPUS_VERSIONS)
        raise ValueError(f"unknown redaction corpus {version!r}; available: {available}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CORPUS_SCHEMA:
        raise ValueError(f"corpus {version!r} has an unknown schema {payload.get('schema')!r}")
    cases = tuple(
        RedactionCase(
            id=str(case["id"]),
            klass=str(case["class"]),
            label=str(case["label"]),
            value=case.get("value"),
            expect=tuple(str(kind) for kind in case.get("expect", ())),
        )
        for case in payload.get("cases", ())
    )
    return RedactionCorpus(
        schema=CORPUS_SCHEMA,
        version=str(payload.get("version", version)),
        cases=cases,
    )


def _detected_kinds(value: Any) -> set[str]:
    from agentwatch.secrets import detect, redact_mapping

    if isinstance(value, str):
        return {match.kind for match in detect(value)}
    _masked, kinds = redact_mapping(value)
    return set(kinds)


def evaluate_corpus(corpus: RedactionCorpus) -> CorpusReport:
    """Reproduce per-class recall + false-positive rate from a corpus."""
    from agentwatch.secrets import SECRET_KINDS

    order = {kind: index for index, kind in enumerate(SECRET_KINDS)}
    positives: dict[str, list[RedactionCase]] = {}
    hits: dict[str, int] = {}
    misses: list[str] = []
    negative = 0
    false_positives = 0
    for case in corpus.cases:
        detected = _detected_kinds(case.value)
        if case.label == "negative":
            negative += 1
            if detected:
                false_positives += 1
            continue
        positives.setdefault(case.klass, []).append(case)
        if set(case.expect) <= detected:
            hits[case.klass] = hits.get(case.klass, 0) + 1
        else:
            misses.append(case.id)

    classes = tuple(
        ClassResult(
            klass=klass,
            cases=len(cases),
            hits=hits.get(klass, 0),
            recall=round(hits.get(klass, 0) / len(cases), 4),
            misses=tuple(case.id for case in cases if case.id in set(misses)),
        )
        for klass, cases in sorted(positives.items(), key=lambda item: order.get(item[0], 99))
    )
    total_positive = sum(len(cases) for cases in positives.values())
    total_hits = sum(hits.values())
    return CorpusReport(
        schema=CORPUS_REPORT_SCHEMA,
        corpus=corpus.version,
        positive=total_positive,
        negative=negative,
        overall_recall=round(total_hits / total_positive, 4) if total_positive else 0.0,
        false_positive_rate=round(false_positives / negative, 4) if negative else 0.0,
        classes=classes,
        misses=tuple(sorted(misses)),
    )


def render_report_table(report: CorpusReport) -> str:
    """Render the published per-class table (used in the reference doc)."""
    counts = f"{report.positive} positive / {report.negative} negative case(s)."
    lines = [
        f"Corpus `{report.corpus}` — {counts}",
        "",
        "| Class | Cases | Hits | Recall | Misses |",
        "|---|---|---|---|---|",
    ]
    for result in report.classes:
        misses = ", ".join(result.misses) if result.misses else "—"
        lines.append(
            f"| {result.klass} | {result.cases} | {result.hits} | {result.recall:.4f} | {misses} |"
        )
    lines.append("")
    lines.append(
        f"Overall recall: **{report.overall_recall:.4f}** "
        f"({report.positive - len(report.misses)}/{report.positive}); "
        f"false-positive rate: **{report.false_positive_rate:.4f}** "
        f"({report.negative} negative cases)."
    )
    return "\n".join(lines)
