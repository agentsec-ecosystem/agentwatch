"""Recorder-state audit records (M16 S5, #239).

The hash chain proves stored records were not altered; it says nothing about
*changing what gets recorded*. ``init``, ``uninstall``, a privacy downgrade, a
retention change, or an export reconfiguration would otherwise leave no trace — a
deliberate uninstall at 14:02 is indistinguishable from an idle laptop.

This module appends **metadata-only** marker records for every recorder-state
transition, using the same marker convention as ``session-purge`` and
``operator-note``: agentwatch-authored (``MARKER_PRODUCER``), append-only, and
never carrying a secret value. The ``coverage-window-open``/``-close`` pair lets a
bundle state *"recording was active from T1 to T2, configured as X."*
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentwatch.configuration import AgentwatchConfig
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.secrets import redact_secrets
from agentwatch.signing import KEY_ROTATION_TOOL
from agentwatch.store import MARKER_PRODUCER, ChainEntry, RecordStore

RECORDER_INSTALLED_TOOL = "recorder-installed"
RECORDER_UNINSTALLED_TOOL = "recorder-uninstalled"
CONFIG_CHANGED_TOOL = "config-changed"
PRIVACY_MODE_CHANGED_TOOL = "privacy-mode-changed"
RETENTION_CHANGED_TOOL = "retention-changed"
EXPORT_CONFIGURED_TOOL = "export-configured"
COVERAGE_WINDOW_OPEN_TOOL = "coverage-window-open"
COVERAGE_WINDOW_CLOSE_TOOL = "coverage-window-close"

MARKER_TOOLS = frozenset(
    {
        RECORDER_INSTALLED_TOOL,
        RECORDER_UNINSTALLED_TOOL,
        CONFIG_CHANGED_TOOL,
        PRIVACY_MODE_CHANGED_TOOL,
        RETENTION_CHANGED_TOOL,
        EXPORT_CONFIGURED_TOOL,
        COVERAGE_WINDOW_OPEN_TOOL,
        COVERAGE_WINDOW_CLOSE_TOOL,
        KEY_ROTATION_TOOL,
    }
)

# Recorder-state markers live in this synthetic session, like `store-access`.
MARKER_SESSION = "agentwatch"

UNKNOWN = "unknown"


@dataclass(frozen=True)
class MarkerReport:
    """Outcome of attempting to append one marker (``coalesced`` writes nothing)."""

    tool: str
    seq: int | None
    coalesced: bool = False


@dataclass(frozen=True)
class RecorderState:
    """The last recorded configuration of the recorder, read from the chain.

    Every field is ``None`` when no marker of that kind has ever been written.
    """

    installed: bool | None = None
    privacy_mode: str | None = None
    retention_days: int | None = None
    export_enabled: bool | None = None
    export_format: str | None = None


@dataclass(frozen=True)
class CoverageWindow:
    """A period during which the recorder was active (open when ``closed_at`` is None)."""

    open_seq: int
    opened_at: datetime
    reason: str | None = None
    close_seq: int | None = None
    closed_at: datetime | None = None

    @property
    def active(self) -> bool:
        """Whether the window was never closed (a crash leaves it open-ended)."""
        return self.closed_at is None


# ---------------------------------------------------------------------------
# Appending markers
# ---------------------------------------------------------------------------


def _append_marker(
    store: RecordStore,
    tool: str,
    arguments: dict[str, Any],
    *,
    now: datetime | None = None,
    outcome: Outcome = Outcome.OK,
) -> ChainEntry:
    record = AgentRecord(
        session_id=MARKER_SESSION,
        agent=AgentIdentity(identity="agentwatch"),
        tool=ToolCall(
            name=tool,
            arguments=arguments,
            privacy_mode=RecordPrivacyMode.METADATA_ONLY,
        ),
        outcome=outcome,
        started_at=now or datetime.now(timezone.utc),
        producer=MARKER_PRODUCER,
    )
    return store.append(record)


def _marker_arguments(store: RecordStore, tool: str) -> list[dict[str, Any]]:
    """Arguments of every already-stored marker of ``tool``, in store order."""
    return [
        entry.record.tool.arguments or {}
        for entry in store.entries()
        if entry.record is not None and entry.record.tool.name == tool
    ]


def record_recorder_installed(
    store: RecordStore,
    *,
    scope: str,
    harness: str | None = None,
    now: datetime | None = None,
) -> MarkerReport:
    """Append one ``recorder-installed`` marker (idempotent per scope+harness)."""
    arguments: dict[str, Any] = {"scope": _clean(scope)}
    if harness is not None:
        arguments["harness"] = _clean(harness)
    last = _marker_arguments(store, RECORDER_INSTALLED_TOOL)
    if last and last[-1] == arguments:
        return MarkerReport(RECORDER_INSTALLED_TOOL, None, coalesced=True)
    entry = _append_marker(store, RECORDER_INSTALLED_TOOL, arguments, now=now)
    return MarkerReport(RECORDER_INSTALLED_TOOL, entry.seq)


def record_recorder_uninstalled(
    store: RecordStore,
    *,
    scope: str,
    harness: str | None = None,
    now: datetime | None = None,
) -> MarkerReport:
    """Append one ``recorder-uninstalled`` marker (idempotent per scope+harness)."""
    arguments: dict[str, Any] = {"scope": _clean(scope)}
    if harness is not None:
        arguments["harness"] = _clean(harness)
    last = _marker_arguments(store, RECORDER_UNINSTALLED_TOOL)
    if last and last[-1] == arguments:
        return MarkerReport(RECORDER_UNINSTALLED_TOOL, None, coalesced=True)
    entry = _append_marker(store, RECORDER_UNINSTALLED_TOOL, arguments, now=now)
    return MarkerReport(RECORDER_UNINSTALLED_TOOL, entry.seq)


def record_config_change(
    store: RecordStore,
    *,
    key: str,
    new: Any,
    old: Any = None,
    now: datetime | None = None,
) -> MarkerReport:
    """Append a generic ``config-changed`` marker (key + old/new, metadata only).

    Values are stringified and passed through the secret redactor, so a config
    value that looks like a credential is masked, never persisted. The change is
    coalesced when the last marker for the same key already carries ``new``.
    """
    clean_key = _clean(key)
    new_text = _clean_value(new)
    old_text = UNKNOWN if old is None else _clean_value(old)
    arguments = {"key": clean_key, "old": old_text, "new": new_text}
    last = _marker_arguments(store, CONFIG_CHANGED_TOOL)
    if last and last[-1].get("key") == clean_key and last[-1].get("new") == new_text:
        return MarkerReport(CONFIG_CHANGED_TOOL, None, coalesced=True)
    entry = _append_marker(store, CONFIG_CHANGED_TOOL, arguments, now=now)
    return MarkerReport(CONFIG_CHANGED_TOOL, entry.seq)


def record_privacy_mode_changed(
    store: RecordStore, *, old: str | None, new: str, now: datetime | None = None
) -> MarkerReport:
    """Append a ``privacy-mode-changed`` marker (coalesced when unchanged)."""
    return _record_transition(
        store,
        PRIVACY_MODE_CHANGED_TOOL,
        {"old": UNKNOWN if old is None else _clean(old), "new": _clean(new)},
        new,
        now=now,
    )


def record_retention_changed(
    store: RecordStore, *, old: int | None, new: int, now: datetime | None = None
) -> MarkerReport:
    """Append a ``retention-changed`` marker (coalesced when unchanged)."""
    return _record_transition(
        store,
        RETENTION_CHANGED_TOOL,
        {"old": UNKNOWN if old is None else str(old), "new": str(new)},
        new,
        now=now,
    )


def record_export_configured(
    store: RecordStore,
    *,
    enabled: bool,
    fmt: str | None = None,
    now: datetime | None = None,
) -> MarkerReport:
    """Append an ``export-configured`` marker (enabled + format; never the endpoint)."""
    arguments: dict[str, Any] = {"enabled": bool(enabled)}
    if fmt is not None:
        arguments["format"] = _clean(fmt)
    last = _marker_arguments(store, EXPORT_CONFIGURED_TOOL)
    if last and last[-1] == arguments:
        return MarkerReport(EXPORT_CONFIGURED_TOOL, None, coalesced=True)
    entry = _append_marker(store, EXPORT_CONFIGURED_TOOL, arguments, now=now)
    return MarkerReport(EXPORT_CONFIGURED_TOOL, entry.seq)


def _record_transition(
    store: RecordStore,
    tool: str,
    arguments: dict[str, Any],
    new: Any,
    *,
    now: datetime | None,
) -> MarkerReport:
    last = _marker_arguments(store, tool)
    if last and last[-1].get("new") == _clean_value(new):
        return MarkerReport(tool, None, coalesced=True)
    entry = _append_marker(store, tool, arguments, now=now)
    return MarkerReport(tool, entry.seq)


def open_coverage_window(
    store: RecordStore, *, reason: str | None = None, now: datetime | None = None
) -> MarkerReport:
    """Open a coverage window unless one is already open."""
    windows = coverage_windows(store)
    if windows and windows[-1].active:
        return MarkerReport(COVERAGE_WINDOW_OPEN_TOOL, None, coalesced=True)
    arguments: dict[str, Any] = {}
    if reason is not None:
        arguments["reason"] = _clean(reason)
    entry = _append_marker(store, COVERAGE_WINDOW_OPEN_TOOL, arguments, now=now)
    return MarkerReport(COVERAGE_WINDOW_OPEN_TOOL, entry.seq)


def close_coverage_window(
    store: RecordStore, *, reason: str | None = None, now: datetime | None = None
) -> MarkerReport:
    """Close the open coverage window; a no-op when none is open."""
    windows = coverage_windows(store)
    if not windows or not windows[-1].active:
        return MarkerReport(COVERAGE_WINDOW_CLOSE_TOOL, None, coalesced=True)
    arguments: dict[str, Any] = {}
    if reason is not None:
        arguments["reason"] = _clean(reason)
    entry = _append_marker(store, COVERAGE_WINDOW_CLOSE_TOOL, arguments, now=now)
    return MarkerReport(COVERAGE_WINDOW_CLOSE_TOOL, entry.seq)


# ---------------------------------------------------------------------------
# Reading markers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecorderMarker:
    """One stored recorder-state marker, for read-side reporting."""

    seq: int
    tool: str
    arguments: dict[str, Any]
    at: datetime


def recorder_markers(store: RecordStore) -> list[RecorderMarker]:
    """Every recorder-state marker, in store order."""
    markers: list[RecorderMarker] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name not in MARKER_TOOLS:
            continue
        markers.append(
            RecorderMarker(
                seq=entry.seq,
                tool=record.tool.name,
                arguments=dict(record.tool.arguments or {}),
                at=record.started_at,
            )
        )
    return markers


def coverage_windows(store: RecordStore) -> list[CoverageWindow]:
    """Pair ``coverage-window-open``/``-close`` markers into windows, in order.

    A window with no matching close is returned open-ended (``active``); a close
    with no open is ignored. This is how S2 distinguishes "complete" from "the
    recorder stopped mid-window".
    """
    windows: list[CoverageWindow] = []
    for marker in recorder_markers(store):
        if marker.tool == COVERAGE_WINDOW_OPEN_TOOL:
            windows.append(
                CoverageWindow(
                    open_seq=marker.seq,
                    opened_at=marker.at,
                    reason=_optional_str(marker.arguments.get("reason")),
                )
            )
        elif marker.tool == COVERAGE_WINDOW_CLOSE_TOOL and windows and windows[-1].active:
            previous = windows[-1]
            windows[-1] = CoverageWindow(
                open_seq=previous.open_seq,
                opened_at=previous.opened_at,
                reason=previous.reason,
                close_seq=marker.seq,
                closed_at=marker.at,
            )
    return windows


def last_state(store: RecordStore) -> RecorderState:
    """The last recorded recorder state, scanning markers newest-first."""
    installed: bool | None = None
    privacy_mode: str | None = None
    retention_days: int | None = None
    export_enabled: bool | None = None
    export_format: str | None = None
    for marker in reversed(recorder_markers(store)):
        if marker.tool == RECORDER_INSTALLED_TOOL and installed is None:
            installed = True
        elif marker.tool == RECORDER_UNINSTALLED_TOOL and installed is None:
            installed = False
        elif marker.tool == PRIVACY_MODE_CHANGED_TOOL and privacy_mode is None:
            privacy_mode = _optional_str(marker.arguments.get("new"))
        elif marker.tool == RETENTION_CHANGED_TOOL and retention_days is None:
            raw = marker.arguments.get("new")
            retention_days = (
                int(raw) if isinstance(raw, (int, str)) and str(raw).isdigit() else None
            )
        elif marker.tool == EXPORT_CONFIGURED_TOOL and export_enabled is None:
            export_enabled = bool(marker.arguments.get("enabled", False))
            export_format = _optional_str(marker.arguments.get("format"))
    return RecorderState(
        installed=installed,
        privacy_mode=privacy_mode,
        retention_days=retention_days,
        export_enabled=export_enabled,
        export_format=export_format,
    )


def reconcile_config(
    store: RecordStore, cfg: AgentwatchConfig, *, now: datetime | None = None
) -> list[MarkerReport]:
    """Append a marker for every recorder setting that changed since it was last read.

    This is how a hand-edited config becomes visible: the next ``init`` or daemon
    start compares the resolved config to the last recorded state and appends
    ``privacy-mode-changed``/``retention-changed``/``export-configured`` markers.
    An unchanged setting is coalesced (no marker).
    """
    state = last_state(store)
    reports: list[MarkerReport] = []
    if state.privacy_mode != cfg.privacy.mode:
        reports.append(
            record_privacy_mode_changed(
                store, old=state.privacy_mode, new=cfg.privacy.mode, now=now
            )
        )
    if state.retention_days != cfg.store.retention_days:
        reports.append(
            record_retention_changed(
                store, old=state.retention_days, new=cfg.store.retention_days, now=now
            )
        )
    if state.export_enabled != cfg.export.enabled or state.export_format != cfg.export.format:
        reports.append(
            record_export_configured(
                store, enabled=cfg.export.enabled, fmt=cfg.export.format, now=now
            )
        )
    return reports


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean(value: str) -> str:
    """Allow-list-ish sanitation for a metadata string (never called on payloads)."""
    text = str(value)
    return "".join(char for char in text if char.isprintable())[:256]


def _clean_value(value: Any) -> str:
    """Stringify and mask a config value before it enters the chain."""
    masked, _kinds = redact_secrets(str(value))
    return masked[:256]


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None
