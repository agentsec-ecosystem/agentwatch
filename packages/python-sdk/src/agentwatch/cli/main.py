"""agentwatch command-line entry point (issue #11).

M1 wired the framework and every documented subcommand so ``agentwatch --help``
lists them. ``status`` is fully implemented; M3 adds ``init``/``uninstall``
(hook installation + daemon lifecycle) and ``sessions``. Remaining commands
land in M4-M5 and fail closed here rather than pretending to succeed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import urllib.request
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentwatch import errors, hook, naming
from agentwatch.aat import aat_version_line, export_aat, to_aat_json, write_aat
from agentwatch.access import (
    DataClass,
    Role,
    access_log,
    access_log_to_json,
    evaluate_access,
    matrix_to_json,
    record_access_decision,
    render_access_log,
    render_matrix,
)
from agentwatch.agent_trace import (
    agent_trace_record,
    cross_validate,
    export_agent_trace,
    read_agent_trace,
    read_agent_trace_notes,
    to_agent_trace_json,
    write_agent_trace,
    write_agent_trace_notes,
)
from agentwatch.annotate import AnnotateError, annotate_session, tagged_sessions
from agentwatch.archive import archive_store, combined_records, verify_archives
from agentwatch.attestation import attest_session
from agentwatch.blame import blame_sessions, build_blame, render_blame
from agentwatch.bom import build_bom, to_agentwatch_json, to_cyclonedx
from agentwatch.capabilities import (
    capabilities_to_json,
    capability_loads,
    detect_capability_changes,
    discover_capabilities,
    record_capability_snapshot,
    render_capabilities,
    render_capability_changes,
)
from agentwatch.compliance import FRAMEWORKS, build_report, render_report
from agentwatch.concurrency import build_concurrency, render_concurrency
from agentwatch.config_explain import explain_config, render_explanations
from agentwatch.configuration import AgentwatchConfig, ConfigError, default_paths, load_config
from agentwatch.cost import BY_OPTIONS, build_cost, render_cost
from agentwatch.coverage import (
    build_coverage,
    default_transcript_base,
    discover_cursor_transcripts,
    discover_transcripts,
)
from agentwatch.demo import purge_demo, render_demo, run_demo
from agentwatch.diff import diff_sessions
from agentwatch.digest import build_digest, render_digest
from agentwatch.doctor import all_passed, run_checks, to_json
from agentwatch.drift import (
    correlate_deployments,
    detect_drift,
    emit_signals,
    load_deployments,
    metric_series,
    signal_to_json,
)
from agentwatch.env_fingerprint import (
    annotate_environment,
    environment_changes,
    group_sessions_by_env,
    render_env_groups,
    session_environments,
)
from agentwatch.evidence import build_bundle, verify_bundle
from agentwatch.explain import explain_session
from agentwatch.fingerprint import group_sessions_by_behavior, render_behavior_groups
from agentwatch.fleet import build_fleet, fleet_to_json, ingest_host, parse_sources, render_fleet
from agentwatch.flow import (
    ContentFlow,
    content_flow_observations,
    detect_flows,
    ensure_key_at,
    record_flow_observations,
    render_flows,
)
from agentwatch.governance import build_notice, render_notice
from agentwatch.health import fetch_health, local_snapshot
from agentwatch.holds import (
    active_holds,
    held_skips,
    parse_scope,
    record_hold_add,
    record_hold_release,
    render_holds,
)
from agentwatch.impact import build_impact, render_impact
from agentwatch.importer import import_transcripts, resolve_paths
from agentwatch.incident_cases import (
    active_cases,
    build_case_bundle,
    case_timeline,
    record_case_add,
    record_case_create,
    record_case_remove,
    render_case_timeline,
    verify_case_bundle,
)
from agentwatch.ingest import resolve_ingest_paths, run_ingest
from agentwatch.install import (
    EVENT_PHASES,
    InstallError,
    detect_claude_version,
    hooks_installed,
    install_hooks,
    is_daemon_alive,
    preflight,
    resolve_hook_command,
    resolve_scope,
    start_daemon,
    start_mcp_proxy,
    stop_daemon,
    stop_mcp_proxy,
    uninstall_hooks,
)
from agentwatch.inventory import build_inventory, inventory_to_json, render_inventory
from agentwatch.managed_policy import detect_managed_policy, install_guidance
from agentwatch.mcp_config import (
    install_mcp_proxy,
    resolve_mcp_proxy_command,
    resolve_mcp_scope,
    uninstall_mcp_proxy,
)
from agentwatch.mcp_server import RateLimiter, serve_stdio
from agentwatch.mcp_surface import (
    detect_surface_changes,
    render_changes,
    render_snapshots,
    survey,
)
from agentwatch.memory import discover_memory_stores, render_memory_stores
from agentwatch.notarize import (
    CheckpointExport,
    dumps,
    export_checkpoint,
    render_checkpoint,
    request_timestamp,
    verify_checkpoint,
)
from agentwatch.ocsf import session_cloudevents, session_ocsf
from agentwatch.outcomes import build_outcomes, render_outcomes
from agentwatch.oversight import BY_OPTIONS as OVERSIGHT_BY_OPTIONS
from agentwatch.oversight import build_oversight, render_oversight
from agentwatch.policy_suggest import (
    TARGETS,
    PolicyParseError,
    load_policy,
    render_policy_suggestion,
    render_whatif,
    simulate_policy,
    suggest_policy,
    suggestion_to_dict,
    whatif_to_dict,
)
from agentwatch.profiles import PROFILE_NAMES, apply_profile, render_profile
from agentwatch.provenance import build_provenance, render_provenance
from agentwatch.quarantine import (
    QuarantineError,
    QuarantineLog,
    clear_entries,
    inspect_entry,
    list_entries,
    requeue_entries,
)
from agentwatch.query import search, since_cutoff
from agentwatch.query_index import (
    ParquetUnavailableError,
    QueryIndex,
    index_path_for_store,
)
from agentwatch.receipts import record_receipt, redact_preview
from agentwatch.recorder_state import (
    close_coverage_window,
    last_state,
    open_coverage_window,
    reconcile_config,
    record_recorder_installed,
    record_recorder_uninstalled,
    record_retention_changed,
)
from agentwatch.records import EVENT_VERSION, SecurityEvent, SecurityEventType, validate_event
from agentwatch.redact import (
    evaluate_corpus,
    load_corpus,
    redaction_config_from_mode,
    render_report_table,
)
from agentwatch.redactor import findings_to_dict
from agentwatch.redactor import redact as redact_value
from agentwatch.release_verify import verify_release
from agentwatch.replay import replay_session
from agentwatch.retention import profile_names, resolve_retention_profile
from agentwatch.runner_segments import (
    anchor_records,
    custody_rows,
    import_segment,
    render_custody,
    seal_segment,
    verify_segment,
)
from agentwatch.secret_trace import render_secrets, trace_secrets
from agentwatch.semconv import version_line
from agentwatch.service import install_service, render_unit, uninstall_service
from agentwatch.session_export import SessionExport, export_session, to_ndjson, write_ndjson
from agentwatch.session_state import session_states
from agentwatch.signing import (
    KEY_FILENAME,
    SigningError,
    load_or_create_key,
    record_key_rotation,
    rotate_key,
    signing_status,
)
from agentwatch.store import RecordStore, repair_store
from agentwatch.store_access import DestinationKind, record_store_access
from agentwatch.tail import Tail, TailLine, follow, render_record
from agentwatch.trace import build_trace, render_trace, replay_trace, trace_to_json
from agentwatch.tree import build_tree, render_tree, sort_by_cost
from agentwatch.ui import ConsoleServer, open_console_url
from agentwatch.union import render_union, union
from agentwatch.verify_privacy import verify_privacy
from agentwatch.view import list_sessions, render_session
from agentwatch.window import DEFAULT_WINDOW, build_window, render_window

# Documented subcommands still deferred to a later milestone
# ([cli-reference](../../../../docs/reference/cli-reference.md)).
DEFERRED_COMMANDS = ("replay", "export", "migrate")

# Exit statuses come from the one error catalog (agentwatch.errors), so the
# published exit-code table cannot drift from the code.
_EXIT_CONFIG_ERROR = errors.exit_code(errors.ErrorCode.CONFIG)
_EXIT_INSTALL_ERROR = errors.exit_code(errors.ErrorCode.INSTALL)
_EXIT_NOT_IMPLEMENTED = errors.exit_code(errors.ErrorCode.NOT_IMPLEMENTED)
_EXIT_USAGE_ERROR = errors.exit_code(errors.ErrorCode.USAGE)


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always present on 3.10+
        return "0.1.0"
    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - editable/source checkout
        return "0.1.0"


def _version_string() -> str:
    """The ``--version`` banner, plus the namesake-distribution warning when detected."""
    banner = f"agentwatch {_version()} ({version_line()}; {aat_version_line()})"
    warning = naming.distribution_warning()
    return f"{banner}\n{warning}" if warning else banner


class _VersionAction(argparse.Action):
    """Print the version banner verbatim (no help-formatter line wrapping)."""

    def __init__(
        self, option_strings: Sequence[str], dest: str, *, version: str = "", **kwargs: Any
    ) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)
        self.version = version

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace | None,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(self.version)
        parser.exit()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentwatch",
        description="Local-first execution observability for AI agents.",
    )
    parser.add_argument("--version", action=_VersionAction, version=_version_string())
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="PATH",
        help="config file that overrides the defaults and environment (repeatable)",
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a config key, e.g. --set log.level=debug (repeatable)",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    init = sub.add_parser("init", help="install hooks + start the daemon (M3)")
    init.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="where to write hooks: project .claude/settings.local.json (default) or user settings",
    )
    init.add_argument(
        "--no-daemon",
        action="store_true",
        help="install hooks only; do not start the daemon",
    )
    init.add_argument(
        "--profile",
        choices=PROFILE_NAMES,
        default=None,
        help="apply a named configuration bundle: solo | team | compliance | ci (M21 S35)",
    )
    init.add_argument(
        "--sync-hooks",
        action="store_true",
        help="install synchronous (blocking) hooks instead of the default async",
    )
    init.add_argument(
        "--dry-run",
        action="store_true",
        help="print the hooks that would be written and write nothing",
    )
    init.add_argument(
        "--yes",
        action="store_true",
        help="assume yes for non-interactive installs",
    )
    init.add_argument(
        "--service",
        action="store_true",
        help="also generate a launchd/systemd user unit to supervise the daemon (M12)",
    )
    init.add_argument(
        "--mcp-proxy",
        action="store_true",
        help="re-point MCP server config at the interposition proxy (M10 N1)",
    )
    init.add_argument(
        "--mcp-scope",
        choices=("project", "user"),
        default="project",
        help="which MCP config to re-point (default: project .mcp.json)",
    )
    init.add_argument(
        "--mcp-servers",
        default=None,
        help="comma-separated MCP server names to re-point (default: all)",
    )
    init.add_argument(
        "--mcp-host", default="127.0.0.1", help="HTTP MCP proxy bind host (default loopback)"
    )
    init.add_argument(
        "--mcp-port", type=int, default=8765, help="HTTP MCP proxy bind port (default 8765)"
    )

    sub.add_parser("status", help="print the resolved configuration / health summary")

    config_cmd = sub.add_parser("config", help="inspect operator configuration (M21 S34)")
    config_sub = config_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    config_explain = config_sub.add_parser(
        "explain", help="show each key's effective value, winning layer, and overrides"
    )
    config_explain.add_argument("key", nargs="?", default=None, help="explain one key only")
    config_explain.add_argument(
        "--diff", action="store_true", help="only keys that differ from defaults"
    )
    config_explain.add_argument("--json", action="store_true", help="emit the explanation as JSON")

    access_cmd = sub.add_parser(
        "access", help="fleet role x data-class read-access model (M29 ACC-1)"
    )
    access_sub = access_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    access_log_p = access_sub.add_parser(
        "log", help="self-visible access log: who read my records, and when"
    )
    access_log_p.add_argument("--owner", required=True, help="whose records to report on")
    access_log_p.add_argument("--json", action="store_true", help="emit the log as JSON")
    access_check_p = access_sub.add_parser(
        "check", help="evaluate a role x data-class read; record it; deny -> nonzero"
    )
    access_check_p.add_argument("--role", choices=[role.value for role in Role], required=True)
    access_check_p.add_argument(
        "--data-class",
        dest="data_class",
        choices=[data.value for data in DataClass],
        required=True,
    )
    access_check_p.add_argument("--owner", required=True, help="whose record is read")
    access_check_p.add_argument("--reader", default=None, help="the reader (default: the owner)")
    access_check_p.add_argument(
        "--same-team", dest="same_team", action="store_true", help="reader is on the owner's team"
    )
    access_check_p.add_argument(
        "--content", dest="content_available", action="store_true", help="content is stored"
    )
    access_check_p.add_argument("--json", action="store_true", help="emit the decision as JSON")
    access_matrix_p = access_sub.add_parser("matrix", help="print the role x data-class matrix")
    access_matrix_p.add_argument("--json", action="store_true", help="emit the matrix as JSON")

    governance_cmd = sub.add_parser(
        "governance", help="governance artifacts from the effective config (M29 ACC-2)"
    )
    governance_sub = governance_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    governance_notice = governance_sub.add_parser(
        "notice",
        help="what is recorded/not, who can see it, retention, erasure (not legal advice)",
    )
    governance_notice.add_argument("--json", action="store_true", help="emit the notice as JSON")

    hold_cmd = sub.add_parser(
        "hold", help="legal holds that suspend retention/purge (M29 HLD-1)"
    )
    hold_sub = hold_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    hold_add = hold_sub.add_parser("add", help="place a hold on a scope")
    hold_add.add_argument(
        "--scope",
        required=True,
        help="session:<id> | project:<path> | principal:<id> | time:<start>..<end>",
    )
    hold_add.add_argument("--reason", required=True, help="why the hold exists (recorded)")
    hold_add.add_argument("--ref", default=None, help="external reference, e.g. CASE-123")
    hold_add.add_argument("--json", action="store_true", help="emit the hold as JSON")
    hold_list = hold_sub.add_parser("list", help="list active holds")
    hold_list.add_argument("--json", action="store_true", help="emit the holds as JSON")
    hold_release = hold_sub.add_parser("release", help="release an active hold")
    hold_release.add_argument("hold_id", help="the hold id, e.g. H17")
    hold_release.add_argument("--reason", default=None, help="why the hold is released")
    hold_release.add_argument("--json", action="store_true", help="emit the result as JSON")

    case_cmd = sub.add_parser(
        "case", help="incident cases: merged timeline + offline bundle (M30 IR-1)"
    )
    case_sub = case_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    case_create = case_sub.add_parser("create", help="create a case (chain-recorded)")
    case_create.add_argument("--title", required=True, help="human-readable case title")
    case_create.add_argument("--severity", default="medium", help="severity label (default medium)")
    case_create.add_argument("--ref", default=None, help="external reference, e.g. INC-123")
    case_create.add_argument("--json", action="store_true", help="emit the case as JSON")
    case_add = case_sub.add_parser("add", help="add a session to a case (chain-recorded)")
    case_add.add_argument("case_id", help="the case id, e.g. C1")
    case_add.add_argument("--session", dest="session", required=True, help="session id to add")
    case_add.add_argument("--json", action="store_true", help="emit the marker as JSON")
    case_remove = case_sub.add_parser("remove", help="remove a session from a case")
    case_remove.add_argument("case_id", help="the case id, e.g. C1")
    case_remove.add_argument(
        "--session", dest="session", required=True, help="session id to remove"
    )
    case_remove.add_argument("--json", action="store_true", help="emit the marker as JSON")
    case_list = case_sub.add_parser("list", help="list cases and their membership")
    case_list.add_argument("--json", action="store_true", help="emit the cases as JSON")
    case_show = case_sub.add_parser("show", help="show a case's merged, gap-annotated timeline")
    case_show.add_argument("case_id", help="the case id, e.g. C1")
    case_show.add_argument("--json", action="store_true", help="emit the timeline as JSON")
    case_export = case_sub.add_parser("export", help="export a case bundle (local, no egress)")
    case_export.add_argument("case_id", help="the case id, e.g. C1")
    case_export.add_argument(
        "--out", default=None, help="write the bundle here (default: <case>.zip)"
    )
    case_export.add_argument("--json", action="store_true", help="emit the result as JSON")
    case_verify = case_sub.add_parser("verify", help="verify a case bundle offline")
    case_verify.add_argument("bundle", help="case bundle zip path")
    case_verify.add_argument("--json", action="store_true", help="emit the verdict as JSON")

    segment_cmd = sub.add_parser(
        "segment", help="sealed runner segments: export/verify/custody (M30 RUN-1)"
    )
    segment_sub = segment_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    segment_export = segment_sub.add_parser(
        "export", help="seal a session's records into a self-verifying segment"
    )
    segment_export.add_argument("--session", dest="session", required=True, help="session id")
    segment_export.add_argument("--runner", required=True, help="runner identity, e.g. ci-runner-7")
    segment_export.add_argument("--run-id", dest="run_id", required=True, help="runner run id")
    segment_export.add_argument(
        "--traceparent", default=None, help="W3C traceparent for the originating session"
    )
    segment_export.add_argument(
        "--out", default=None, help="write the segment here (default: <session>.segment.zip)"
    )
    segment_export.add_argument("--json", action="store_true", help="emit the result as JSON")
    segment_verify = segment_sub.add_parser("verify", help="verify a sealed segment offline")
    segment_verify.add_argument("bundle", help="segment zip path")
    segment_verify.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    segment_custody = segment_sub.add_parser(
        "custody", help="label records local-witnessed vs imported runner"
    )
    segment_custody.add_argument("--json", action="store_true", help="emit the rows as JSON")

    import_segment_cmd = sub.add_parser(
        "import-segment", help="verify and anchor a sealed runner segment (M30 RUN-1)"
    )
    import_segment_cmd.add_argument("bundle", help="segment zip path")
    import_segment_cmd.add_argument("--json", action="store_true", help="emit the report as JSON")

    union_cmd = sub.add_parser(
        "union", help="read-time union of hook records and SDK spans (M21 S11)"
    )
    union_cmd.add_argument(
        "--session-id", dest="session_id", default=None, help="only this session"
    )
    union_cmd.add_argument(
        "--source", choices=("hook", "sdk"), default=None, help="only this source"
    )
    union_cmd.add_argument("--json", action="store_true", help="emit the union as JSON")

    checkpoint_cmd = sub.add_parser(
        "checkpoint", help="export a checkpoint digest, optionally signed/timestamped (M22 W7/W9)"
    )
    checkpoint_sub = checkpoint_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    checkpoint_export = checkpoint_sub.add_parser(
        "export", help="emit the latest checkpoint digest (optionally signed / RFC 3161 stamped)"
    )
    checkpoint_export.add_argument(
        "--sign", action="store_true", help="sign the digest with this installation's key"
    )
    checkpoint_export.add_argument(
        "--tsa", default=None, help="RFC 3161 TSA URL for an optional timestamp token"
    )
    checkpoint_export.add_argument("--output", default=None, help="write to a file")
    checkpoint_export.add_argument("--json", action="store_true", help="emit as JSON")
    checkpoint_verify = checkpoint_sub.add_parser(
        "verify", help="verify a signed checkpoint export with a public key"
    )
    checkpoint_verify.add_argument("file", help="checkpoint export JSON file")
    checkpoint_verify.add_argument(
        "--public-key", required=True, help="path to the raw ed25519 public key"
    )
    checkpoint_verify.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    checkpoint_rotate = checkpoint_sub.add_parser(
        "rotate", help="rotate this installation's signing key (recorded as a chain event)"
    )
    checkpoint_rotate.add_argument("--json", action="store_true", help="emit the result as JSON")
    sessions = sub.add_parser("sessions", help="list recorded sessions (M3)")
    sessions.add_argument("--project", default=None, help="only sessions in this project (cwd)")
    sessions.add_argument(
        "--tag", default=None, help="only sessions with this operator-note tag (M15)"
    )
    sessions.add_argument(
        "--group-by-behavior",
        dest="group_by_behavior",
        action="store_true",
        help="group sessions by their behavior fingerprint (M17 S7)",
    )
    sessions.add_argument(
        "--group-by-env",
        dest="group_by_env",
        action="store_true",
        help="group sessions by their environment fingerprint (M30 ENV-1)",
    )
    sub.add_parser("verify-privacy", help="verify redaction and scan the store for leaks (M5)")
    completions = sub.add_parser("completions", help="print a shell completion script (M5)")
    completions.add_argument("shell", choices=("bash", "zsh", "fish"))

    doctor = sub.add_parser("doctor", help="run an ordered health checklist with fix hints (M5)")
    doctor.add_argument("--json", action="store_true", help="emit the checklist as JSON")

    tail = sub.add_parser("tail", help="print a read-only stream of records (M5)")
    tail.add_argument("-f", "--follow", action="store_true", help="follow new records (1 s poll)")
    tail.add_argument("--session-id", default=None, help="only show records for this session")
    tail.add_argument("--project", default=None, help="only show records for this project (cwd)")
    tail.add_argument("--json", action="store_true", help="emit one JSON object per record")
    tail.add_argument(
        "--alert", action="store_true", help="mark security signals with an ALERT prefix (M8 H5)"
    )

    event = sub.add_parser("event", help="emit a validated security event (M5 B2)")
    event_sub = event.add_subparsers(dest="action", metavar="ACTION", required=True)
    emit = event_sub.add_parser("emit", help="emit a security event to the daemon")
    emit.add_argument(
        "type",
        choices=[member.value for member in SecurityEventType],
        help="security event type",
    )
    emit.add_argument("--session-id", dest="session_id", help="session to attach the event to")
    emit.add_argument("--tool", help="tool the event concerns")
    emit.add_argument("--reason", help="human-readable reason")
    emit.add_argument("--evidence", help="JSON object of supporting evidence")

    replay = sub.add_parser("replay", help="reconstruct a session timeline (M5)")
    replay.add_argument("session_id", help="session id to replay")
    replay.add_argument(
        "--receipts", action="store_true", help="show what redaction did per record (M15 S32)"
    )
    replay.add_argument(
        "--trace",
        action="store_true",
        help="follow traceparent across hosts/sessions (M26 TRACE-2)",
    )
    replay.add_argument("--json", action="store_true", help="emit records + receipts as JSON")

    redact = sub.add_parser("redact", help="preview or filter redaction (M15 S32; filter M21 S13)")
    redact.add_argument(
        "--preview",
        default=None,
        metavar="SAMPLE",
        help="sample text or JSON to preview; omit to filter stdin to stdout",
    )
    redact.add_argument(
        "--mode",
        choices=("metadata-only", "truncated", "hashed", "full"),
        default=None,
        help="privacy mode for the filter (default: active config)",
    )
    redact.add_argument("--json", action="store_true", help="emit findings as JSON")
    redact.add_argument(
        "target",
        nargs="?",
        default=None,
        help="'eval' to run the public redaction corpus and print per-class numbers",
    )
    redact.add_argument(
        "--corpus",
        default=None,
        metavar="VERSION",
        help="redaction corpus version for 'redact eval' (default: v1)",
    )

    export_session_cmd = sub.add_parser(
        "export-session", help="export one session as NDJSON with its chain segment (M13 J2)"
    )
    export_session_cmd.add_argument("session_id", help="session id to export")
    export_session_cmd.add_argument(
        "--format",
        choices=("ndjson", "ocsf", "cloudevents", "aat", "agent-trace"),
        default="ndjson",
        help=(
            "export format (default: ndjson; ocsf/cloudevents map events; aat is IETF AAT; "
            "agent-trace is the pinned Agent Trace RFC)"
        ),
    )
    export_session_cmd.add_argument(
        "--output", default=None, help="write to a file instead of stdout"
    )
    export_session_cmd.add_argument(
        "--write-notes",
        dest="write_notes",
        default=None,
        metavar="REPO",
        help=(
            "explicitly write Agent Trace notes into REPO (requires --format agent-trace); "
            "the default export never writes to a repository"
        ),
    )

    view = sub.add_parser("view", help="terminal timeline of a session (M7)")
    view.add_argument(
        "session_id", nargs="?", default=None, help="session id (omit to list sessions)"
    )

    explain = sub.add_parser("explain", help="summarize a session (deterministic, local-first)")
    explain.add_argument("session_id", help="session id to summarize")

    impact = sub.add_parser("impact", help="a session's change footprint / blast radius (M17 S3)")
    impact.add_argument("session_id", help="session id to footprint")
    impact.add_argument("--since", default=None, help="relative (2d/12h/30m) or ISO timestamp")
    impact.add_argument("--json", action="store_true", help="emit the footprint as JSON")

    blame = sub.add_parser("blame", help="who touched a path, newest first (M17 S18)")
    blame.add_argument("path", help="file path (relative paths are resolved against --project)")
    blame.add_argument("--since", default=None, help="relative (30d/12h/30m) or ISO timestamp")
    blame.add_argument("--project", default=None, help="project root for normalization/filtering")
    blame.add_argument(
        "--sessions", action="store_true", help="print only the distinct session ids"
    )
    blame.add_argument("--json", action="store_true", help="emit the hits as JSON")

    provenance = sub.add_parser(
        "provenance",
        help="which sessions produced a commit/range/PR/file (M30 PRV-1)",
    )
    provenance.add_argument(
        "target", help="<commit|range|PR|file[:lines]>, e.g. abc1234, a..b, PR42, src/app.py:3-5"
    )
    provenance.add_argument("--repo", default=None, help="git repository root (default: cwd)")
    provenance.add_argument("--project", default=None, help="project root for relative paths")
    provenance.add_argument(
        "--window",
        default="7d",
        help="how far back to look for a session (default 7d)",
    )
    provenance.add_argument(
        "--notes",
        default=None,
        metavar="REPO",
        help="cross-validate against existing Agent Trace / git-ai notes in REPO",
    )

    concurrency = sub.add_parser(
        "concurrency",
        help="sessions overlapping in time on the same paths (M30 CNC-1)",
    )
    concurrency.add_argument("--project", default=None, help="project root to scope the report")
    concurrency.add_argument("--since", default=None, help="relative (7d/12h) or ISO timestamp")
    concurrency.add_argument("--json", action="store_true", help="emit the report as JSON")
    provenance.add_argument("--json", action="store_true", help="emit the report as JSON")

    tree_cmd = sub.add_parser("tree", help="the subagent fan-out of a session (M17 S17)")
    tree_cmd.add_argument("session_id", help="session id to render as a tree")
    tree_cmd.add_argument(
        "--by-cost", dest="by_cost", action="store_true", help="order siblings by cost"
    )
    tree_cmd.add_argument("--json", action="store_true", help="emit the tree as JSON")

    trace_cmd = sub.add_parser("trace", help="reconstruct a cross-host causal trace (M26 TRACE-2)")
    trace_cmd.add_argument("trace_id", help="W3C trace id to reconstruct")
    trace_cmd.add_argument("--json", action="store_true", help="emit the trace as JSON")

    at_cmd = sub.add_parser("at", help="every record in a cross-session time window (M17 S24)")
    at_cmd.add_argument("moment", help='moment, e.g. "2026-10-02 14:00" (local) or an ISO offset')
    at_cmd.add_argument("--window", default=DEFAULT_WINDOW, help="window size (default 30m)")
    at_cmd.add_argument("--json", action="store_true", help="emit the window as JSON")

    digest_cmd = sub.add_parser("digest", help="a local weekly markdown readout (M17 S37)")
    digest_cmd.add_argument("--since", default="7d", help="window to summarize (default 7d)")

    flow_cmd = sub.add_parser("flow", help="content -> argument flow edges of a session (M18 S22)")
    flow_cmd.add_argument("session_id", help="session id to analyse")
    flow_cmd.add_argument(
        "--record",
        action="store_true",
        help="append metadata-only content-flow observations to the store",
    )
    flow_cmd.add_argument("--json", action="store_true", help="emit the edges as JSON")

    secrets_cmd = sub.add_parser("secrets", help="trace exposed secrets across a session (M18 S23)")
    secrets_cmd.add_argument(
        "--session-id", dest="session_id", default=None, help="only this session"
    )
    secrets_cmd.add_argument("--json", action="store_true", help="emit the traces as JSON")

    demo_cmd = sub.add_parser("demo", help="prove the hook->daemon->store pipeline (M19 S31)")
    demo_cmd.add_argument(
        "--purge",
        action="store_true",
        help="tombstone the demo session instead of running",
    )
    demo_cmd.add_argument("--json", action="store_true", help="emit the demo result as JSON")

    search = sub.add_parser("search", help="filter stored records (M8 H3)")
    search.add_argument("--tool", default=None, help="only records for this tool")
    search.add_argument("--outcome", default=None, help="only records with this outcome")
    search.add_argument("--session", dest="session_id", default=None, help="only this session")
    search.add_argument("--project", default=None, help="only records for this project (cwd)")
    search.add_argument(
        "--producer",
        default=None,
        choices=("hook", "import", "event", "ingest", "proxy", "sdk", "demo"),
        help="only records with this provenance kind (M15 S26)",
    )
    search.add_argument(
        "--approval",
        default=None,
        choices=(
            # legacy S14 values
            "user",
            "auto",
            "not-required",
            "denied",
            "unknown",
            # authorization v2 sources (M29 APV-1)
            "human-once",
            "human-remembered",
            "rule",
            "classifier",
            "hook",
            "bypass",
        ),
        help="only records with this authorization decision/source (M19 S14, M29 APV-1)",
    )
    search.add_argument(
        "--mode",
        dest="permission_mode",
        default=None,
        choices=(
            "default",
            "acceptEdits",
            "plan",
            "auto",
            "dontAsk",
            "bypassPermissions",
            "unknown",
        ),
        help="only records with this permission mode in force (M29 APV-2)",
    )
    search.add_argument("--since", default=None, help="relative (2d/12h/30m) or ISO timestamp")
    search.add_argument(
        "--identity",
        default=None,
        help="only records whose agent/principal/workload/delegation handle matches (IDN-2)",
    )
    search.add_argument(
        "--mcp-resource",
        default=None,
        help="only records that read or link this MCP resource URI (MCP-2)",
    )
    search.add_argument(
        "--memory",
        dest="memory",
        action="store_true",
        help="only agent memory read/write/delete records (DET-7)",
    )
    search.add_argument(
        "--capability",
        default=None,
        help="loads of this capability plus calls after the load (M30 CAP-3)",
    )
    search.add_argument(
        "--memory-store",
        dest="memory_store",
        default=None,
        help="writes to this memory store plus calls after the write (M30 MEM-1)",
    )
    search.add_argument("--json", action="store_true", help="emit one JSON object per record")

    index_cmd = sub.add_parser(
        "index", help="embedded rebuildable query index (M30 LUI-2, ADR-0035)"
    )
    index_sub = index_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    index_rebuild = index_sub.add_parser(
        "rebuild", help="rebuild the derived index from the chain store (bit-for-bit)"
    )
    index_status = index_sub.add_parser("status", help="show index presence and freshness")
    index_drop = index_sub.add_parser("drop", help="delete the derived index (chain untouched)")
    index_export = index_sub.add_parser(
        "export-parquet", help="columnar export for notebooks (optional parquet extra)"
    )
    index_export.add_argument("output", help="destination .parquet path")
    index_export.add_argument(
        "--session", dest="session_id", default=None, help="only this session"
    )
    for _index_parser in (index_rebuild, index_status, index_drop, index_export):
        _index_parser.add_argument("--json", action="store_true", help="emit the result as JSON")

    ui_cmd = sub.add_parser(
        "ui", help="read-only loopback console over the store (M30 LUI-1, ADR-0036)"
    )
    ui_cmd.add_argument(
        "--host", default="127.0.0.1", help="loopback bind host (non-loopback is refused)"
    )
    ui_cmd.add_argument("--port", type=int, default=0, help="bind port (0 = ephemeral)")
    ui_cmd.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        default=True,
        help="do not open a browser window",
    )
    ui_cmd.add_argument(
        "--check",
        action="store_true",
        help="start, verify readiness on loopback, and exit (CI smoke / <=60s gate)",
    )

    diff = sub.add_parser("diff", help="behavioral diff of two sessions (M8 H2)")
    diff.add_argument("a", help="first session id")
    diff.add_argument("b", help="second session id")
    diff.add_argument("--json", action="store_true", help="emit the diff as JSON")

    import_cmd = sub.add_parser("import", help="import Claude Code transcripts (M8 H1)")
    import_cmd.add_argument("path", help="transcript file or directory")
    import_cmd.add_argument(
        "--capture",
        choices=("metadata-only", "truncated", "hashed", "full"),
        default="metadata-only",
        help="how much tool content to capture (default: metadata-only)",
    )
    import_cmd.add_argument("--json", action="store_true", help="emit the import stats as JSON")

    ingest = sub.add_parser(
        "ingest", help="ingest foreign OTel/NDJSON/AAT traces (M10 N2, M26 AAT-3)"
    )
    ingest.add_argument("path", help="source file or directory")
    ingest.add_argument(
        "--format",
        choices=(
            "otel",
            "otlp-grpc",
            "ndjson",
            "aat",
            "claude-compliance",
            "claude-otel",
            "system-ingest",
            "acs",
        ),
        default="otel",
        help="foreign trace format (default: otel; aat is IETF Agent Audit Trail; "
        "claude-otel is Claude Code native OTel (CCO-1); claude-compliance is an "
        "Anthropic Compliance API export, requires --consent; system-ingest is the "
        "Linux-only opt-in system-effects layer (SYS-1), requires --consent; acs is "
        "an ACS Guardian audit trail (ACS-1))",
    )
    ingest.add_argument(
        "--consent",
        action="store_true",
        help="explicit opt-in for the egress-adjacent claude-compliance pull (M27 CCA-1) "
        "and the Linux-only system-effects layer (M29 SYS-1)",
    )
    ingest.add_argument(
        "--agent",
        choices=("codex", "opencode"),
        default=None,
        help="read a harness's native logs instead of --format "
        "(codex = rollout JSONL / .jsonl.zst; opencode = storage tree, M27 COD-1/LOG-1)",
    )
    ingest.add_argument(
        "--capture",
        choices=("metadata-only", "truncated", "hashed", "full"),
        default="metadata-only",
        help="how much attribute content to capture (default: metadata-only)",
    )
    ingest.add_argument("--json", action="store_true", help="emit the ingest stats as JSON")

    drift = sub.add_parser("drift", help="trailing-baseline drift signals (M11 R13)")
    drift.add_argument(
        "--metric",
        choices=("records", "errors", "denied", "duration"),
        default="errors",
        help="which stored metric to track (default: errors)",
    )
    drift.add_argument(
        "--bucket",
        choices=("session", "hour"),
        default="session",
        help="how to bucket records into samples (default: session)",
    )
    drift.add_argument("--window", type=int, default=10, help="trailing baseline window")
    drift.add_argument(
        "--z-threshold", type=float, default=3.0, dest="z_threshold", help="z-score threshold"
    )
    drift.add_argument(
        "--min-samples",
        type=int,
        default=5,
        dest="min_samples",
        help="minimum samples before firing",
    )
    drift.add_argument(
        "--emit", action="store_true", help="emit drift-detected events to the daemon (never gates)"
    )
    drift.add_argument("--deploys", default=None, help="JSON/JSONL deployment markers to correlate")
    drift.add_argument(
        "--deploy-window",
        type=float,
        default=3600.0,
        dest="deploy_window",
        help="seconds before a shift within which a deploy is correlated",
    )
    drift.add_argument("--json", action="store_true", help="emit the signals as JSON")

    fleet = sub.add_parser("fleet", help="opt-in multi-host fleet aggregation (M11 R13)")
    fleet_sub = fleet.add_subparsers(dest="action", metavar="ACTION", required=True)
    fleet_ingest = fleet_sub.add_parser(
        "ingest", help="ingest host record stores into this self-hosted store"
    )
    fleet_ingest.add_argument("sources", nargs="+", metavar="HOST=PATH", help="host record stores")
    fleet_show = fleet_sub.add_parser("show", help="show the fleet rollup")
    fleet_show.add_argument("--json", action="store_true", help="emit the snapshot as JSON")
    fleet_show.add_argument(
        "--no-group-by-host",
        action="store_true",
        help="aggregate across hosts (single rollup set)",
    )

    inventory = sub.add_parser("inventory", help="list recorded agents + MCP servers (M9 R9)")
    inventory.add_argument("--session-id", default=None, help="only this session")
    inventory.add_argument("--project", default=None, help="only this project (cwd)")
    inventory.add_argument("--json", action="store_true", help="emit the inventory as JSON")
    inventory.add_argument(
        "--snapshot",
        action="store_true",
        help="current observed MCP tool surface per server (M20 S4)",
    )
    inventory.add_argument(
        "--diff",
        action="store_true",
        help="MCP tool-surface changes over time (M20 S4)",
    )
    inventory.add_argument("--server", default=None, help="only this MCP server (with --diff)")
    inventory.add_argument(
        "--capabilities",
        action="store_true",
        help="list loadable capabilities with content digests (M30 CAP-1)",
    )
    inventory.add_argument(
        "--since",
        default=None,
        help="only capability changes at/after this window (with --capabilities --diff)",
    )
    inventory.add_argument(
        "--memory",
        action="store_true",
        help="list memory stores with digest/size/last-changed (M30 MEM-1)",
    )

    coverage_cmd = sub.add_parser(
        "coverage", help="reconcile the store against transcript ground truth (M16 S2)"
    )
    coverage_cmd.add_argument(
        "--since", default=None, help="relative (2d/12h/30m) or ISO timestamp"
    )
    coverage_cmd.add_argument("--project", default=None, help="only records for this project (cwd)")
    coverage_cmd.add_argument(
        "--session", dest="session_id", default=None, help="only this session"
    )
    coverage_cmd.add_argument(
        "--transcripts",
        default=None,
        help="transcript directory to use as ground truth (default: ~/.claude/projects)",
    )
    coverage_cmd.add_argument(
        "--harness",
        choices=("claude-code", "cursor"),
        default="claude-code",
        help="ground-truth source for reconciliation (default: claude-code)",
    )
    coverage_cmd.add_argument("--json", action="store_true", help="emit the coverage as JSON")

    oversight_cmd = sub.add_parser(
        "oversight", help="authorization + human-oversight facts (M29 APV-3)"
    )
    oversight_cmd.add_argument(
        "--since", default=None, help="relative (2d/12h/30m) or ISO timestamp"
    )
    oversight_cmd.add_argument(
        "--project", default=None, help="only records for this project (cwd)"
    )
    oversight_cmd.add_argument(
        "--by",
        choices=OVERSIGHT_BY_OPTIONS,
        default="source",
        help="group the authorization mix by this dimension (default: source)",
    )
    oversight_cmd.add_argument("--json", action="store_true", help="emit the report as JSON")

    compliance_cmd = sub.add_parser("compliance", help="offline compliance reports (M26 CMP-1)")
    compliance_sub = compliance_cmd.add_subparsers(dest="compliance_command", required=True)
    compliance_report = compliance_sub.add_parser(
        "report", help="render control -> evidence -> verdict rows for a framework"
    )
    compliance_report.add_argument(
        "--framework",
        choices=FRAMEWORKS,
        default="generic",
        help="framework template (default: generic)",
    )
    compliance_report.add_argument(
        "--period", default=None, help="reporting window label (informational)"
    )
    compliance_report.add_argument("--out", default=None, help="write the report to this file")
    compliance_report.add_argument("--json", action="store_true", help="emit the report as JSON")

    cost_cmd = sub.add_parser("cost", help="roll up captured token usage to cost (M17 S6)")
    cost_cmd.add_argument(
        "--by",
        choices=BY_OPTIONS,
        default="session",
        help="rollup dimension (default: session)",
    )
    cost_cmd.add_argument("--since", default=None, help="relative (30d/12h/30m) or ISO timestamp")
    cost_cmd.add_argument(
        "--per",
        choices=("retained-change",),
        default=None,
        help="report a per-unit ratio (--per retained-change; OUT-1)",
    )
    cost_cmd.add_argument(
        "--repo", default=None, help="git repository root for --per retained-change"
    )
    cost_cmd.add_argument("--json", action="store_true", help="emit the rollup as JSON")

    outcomes_cmd = sub.add_parser(
        "outcomes",
        help="deterministic outcome facts: test/build/lint, retained, retries (M30 OUT-1)",
    )
    outcomes_cmd.add_argument(
        "--by",
        choices=("session", "project", "model", "harness"),
        default="project",
        help="rollup dimension (default: project)",
    )
    outcomes_cmd.add_argument(
        "--since", default=None, help="relative (30d/12h/30m) or ISO timestamp"
    )
    outcomes_cmd.add_argument(
        "--repo", default=None, help="git repository root to compute retained changes"
    )
    outcomes_cmd.add_argument("--json", action="store_true", help="emit the facts as JSON")

    bom = sub.add_parser("bom", help="Agent Bill of Materials, CycloneDX (M15 S9)")
    bom_scope = bom.add_mutually_exclusive_group()
    bom_scope.add_argument(
        "--session-id", dest="session_id", default=None, help="only this session"
    )
    bom_scope.add_argument("--project", default=None, help="only this project (cwd)")
    bom_scope.add_argument("--machine", action="store_true", help="all records (default)")
    bom.add_argument(
        "--format",
        choices=("cyclonedx", "json"),
        default="cyclonedx",
        help="output format (default: cyclonedx)",
    )

    retention = sub.add_parser("retention", help="store retention controls (M9 R11)")
    retention_sub = retention.add_subparsers(dest="action", metavar="ACTION", required=True)
    retention_apply = retention_sub.add_parser(
        "apply", help="tombstone records older than the retention window (profile)"
    )
    retention_apply.add_argument(
        "--profile",
        choices=profile_names(),
        default=None,
        help="retention profile: high-risk-12mo (365d, AAT §9), general-6mo (180d), "
        "or custom (store.retention_days; default)",
    )
    retention_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be tombstoned (and which records a hold skips); change nothing",
    )
    retention_apply.add_argument(
        "--json", action="store_true", help="emit the retention report as JSON"
    )

    purge = sub.add_parser("purge", help="tombstone every record of one session (M9 I5)")
    purge.add_argument("session_id", help="session id to purge")
    purge.add_argument("--yes", action="store_true", help="confirm irreversible tombstoning")
    purge.add_argument(
        "--reason", default=None, help="metadata-only reason recorded with the purge"
    )
    purge.add_argument(
        "--override-reason",
        dest="override_reason",
        default=None,
        help="proceed despite an active legal hold; the stated reason is recorded (conspicuous)",
    )

    quarantine_cmd = sub.add_parser(
        "quarantine", help="operator tooling for the quarantine (M16 S27)"
    )
    quarantine_sub = quarantine_cmd.add_subparsers(dest="action", metavar="ACTION", required=True)
    quarantine_list = quarantine_sub.add_parser(
        "list", help="list quarantined entries (reason + time; no payload)"
    )
    quarantine_list.add_argument("--json", action="store_true", help="emit the list as JSON")
    quarantine_inspect = quarantine_sub.add_parser(
        "inspect", help="show one entry (redacted by default)"
    )
    quarantine_inspect.add_argument("entry_id", help="quarantine entry id")
    quarantine_inspect.add_argument(
        "--raw", action="store_true", help="show the unredacted payload (recorded as an access)"
    )
    quarantine_inspect.add_argument("--json", action="store_true", help="emit the entry as JSON")
    quarantine_requeue = quarantine_sub.add_parser(
        "requeue", help="re-run entries through the current adapter"
    )
    quarantine_requeue.add_argument("entry_ids", nargs="*", help="entry ids to requeue")
    quarantine_requeue.add_argument(
        "--all", dest="all_entries", action="store_true", help="requeue every entry"
    )
    quarantine_requeue.add_argument("--json", action="store_true", help="emit the report as JSON")
    quarantine_clear = quarantine_sub.add_parser(
        "clear", help="delete every quarantined entry (explicit)"
    )
    quarantine_clear.add_argument("--yes", action="store_true", help="confirm deletion")

    annotate = sub.add_parser("annotate", help="append an operator note to a session (M15 S20)")
    annotate.add_argument("session_id", help="session id to annotate")
    annotate.add_argument(
        "--note", required=True, help="operator note text (redacted before storage)"
    )
    annotate.add_argument("--tag", default=None, help="optional tag for filtering (sessions --tag)")
    annotate.add_argument(
        "--incident-tag",
        action="append",
        default=None,
        metavar="TAG",
        help="optional incident-registry tag (repeatable; metadata-only, M27 COR-2)",
    )

    export = sub.add_parser("export", help="opt-in OTLP export (M5)")
    export_sub = export.add_subparsers(dest="action", metavar="ACTION", required=True)
    export_sub.add_parser("enable", help="enable export")
    export_sub.add_parser("disable", help="disable export")

    verify_store = sub.add_parser("verify-store", help="check the store hash chain (M4)")
    verify_store.add_argument(
        "--repair", action="store_true", help="rebuild the chain from the intact prefix (F4)"
    )
    verify_store.add_argument("--yes", action="store_true", help="confirm an irreversible repair")

    archive_cmd = sub.add_parser(
        "archive", help="seal an old chain prefix into an archive segment (M16 S28)"
    )
    archive_cmd.add_argument(
        "--before",
        required=True,
        help="archive entries older than this (relative 30d/ISO timestamp)",
    )
    archive_cmd.add_argument(
        "--out", default=None, help="archive directory (default: <store>/archives)"
    )
    archive_cmd.add_argument("--json", action="store_true", help="emit the report as JSON")

    evidence = sub.add_parser(
        "evidence", help="build or verify an offline-verifiable evidence bundle (M15 S1)"
    )
    evidence.add_argument("target", help="session id to bundle, or 'verify'")
    evidence.add_argument(
        "bundle", nargs="?", default=None, help="bundle.zip when target is 'verify'"
    )
    evidence.add_argument(
        "--out", default=None, help="write the bundle here (default: <session>.zip)"
    )
    evidence.add_argument(
        "--include-bom", dest="include_bom", action="store_true", help="include bom.cdx.json (S9)"
    )
    evidence.add_argument(
        "--include",
        dest="include",
        action="append",
        default=None,
        metavar="MEMBER",
        help="extra bundle member: incident-report.json (COR-3)",
    )
    evidence.add_argument(
        "--redact-paths", dest="redact_paths", action="store_true", help="mask filesystem paths"
    )
    verify_release_cmd = sub.add_parser(
        "verify-release", help="verify a built release (SBOM, checksums, signing)"
    )
    verify_release_cmd.add_argument(
        "directory", nargs="?", default="dist", help="release directory (default: dist)"
    )
    verify_release_cmd.add_argument("--checksums", default=None, help="checksums file path")
    verify_release_cmd.add_argument("--sbom", default=None, help="CycloneDX SBOM path")
    verify_release_cmd.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="do not require a signature (local/dry-run only)",
    )
    verify_release_cmd.add_argument("--json", action="store_true", help="emit the report as JSON")
    verify_release_cmd.add_argument(
        "--cosign-identity-regexp", default=None, help="pin the signing identity (keyless cosign)"
    )
    verify_release_cmd.add_argument(
        "--cosign-issuer", default=None, help="pin the OIDC issuer (keyless cosign)"
    )
    migrate = sub.add_parser("migrate", help="store-format migration (M9+)")
    migrate.add_argument("--rollback", action="store_true", help="roll back the last migration")

    uninstall = sub.add_parser("uninstall", help="remove hooks and stop the daemon (M3)")
    uninstall.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="which hooks to remove (default: project)",
    )
    uninstall.add_argument(
        "--mcp-scope",
        choices=("project", "user"),
        default="project",
        help="which MCP config to restore (default: project)",
    )

    mcp = sub.add_parser("mcp-proxy", help="run the MCP interposition proxy (M10 N1)")
    mcp.add_argument("--server", default=None, help="stdio mode: MCP server name (tool.server)")
    mcp.add_argument("--socket", default=None, help="daemon socket path override")
    mcp.add_argument("--http", action="store_true", help="serve HTTP routes instead of stdio")
    mcp.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default loopback)")
    mcp.add_argument(
        "--port", type=int, default=8765, help="HTTP bind port (default 8765; 0 = ephemeral)"
    )
    mcp.add_argument(
        "--transport",
        default="streamable-http",
        help="HTTP transport: streamable-http (default) or http-sse (legacy, deprecated-in-spec)",
    )
    mcp.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="HTTP route (repeatable): MCP server name to upstream URL",
    )
    mcp.add_argument(
        "server_command", nargs=argparse.REMAINDER, help="-- <server command> [args...]"
    )

    a2a = sub.add_parser("a2a-proxy", help="run the A2A interposition proxy (M29 A2A-1)")
    a2a.add_argument("--agent", default=None, help="stdio mode: A2A agent name (tool.server)")
    a2a.add_argument("--socket", default=None, help="daemon socket path override")
    a2a.add_argument("--remote-org", default=None, help="remote organization (delegation)")
    a2a.add_argument("--http", action="store_true", help="serve HTTP routes instead of stdio")
    a2a.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default loopback)")
    a2a.add_argument(
        "--port", type=int, default=8766, help="HTTP bind port (default 8766; 0 = ephemeral)"
    )
    a2a.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="HTTP route (repeatable): A2A agent name to upstream URL",
    )
    a2a.add_argument(
        "agent_command", nargs=argparse.REMAINDER, help="-- <agent command> [args...]"
    )

    mcp_serve = sub.add_parser(
        "mcp-serve", help="read-only MCP server over the record (M30 AGI-1; off by default)"
    )
    mcp_serve.add_argument(
        "--enable",
        action="store_true",
        help="consent-first opt-in; required because the server is off by default",
    )
    mcp_serve.add_argument(
        "--rate-limit",
        type=int,
        default=240,
        help="max tool calls per minute (default 240)",
    )

    suggest_policy_p = sub.add_parser(
        "suggest-policy",
        help="advisory least-privilege permission candidates from history (M30 POL-1)",
    )
    suggest_policy_p.add_argument("--since", default="30d", help="window (default 30d)")
    suggest_policy_p.add_argument("--project", default=None, help="only records for this project")
    suggest_policy_p.add_argument(
        "--target", choices=TARGETS, default="claude-settings", help="output target"
    )
    suggest_policy_p.add_argument(
        "--include",
        action="store_true",
        help="allow destructive/network/credential-adjacent rules (still annotated)",
    )
    suggest_policy_p.add_argument(
        "--out", default=None, help="write the artifact here (nothing else is written)"
    )
    suggest_policy_p.add_argument("--json", action="store_true", help="emit the artifact as JSON")

    what_if = sub.add_parser(
        "what-if",
        help="replay a candidate policy over history (M30 POL-2; simulation only)",
    )
    what_if.add_argument("policy_file", help="path to a policy JSON file")
    what_if.add_argument("--since", default="30d", help="window (default 30d)")
    what_if.add_argument("--project", default=None, help="only records for this project")
    what_if.add_argument("--json", action="store_true", help="emit the simulation as JSON")

    return parser


def _parse_overrides(items: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise ConfigError(f"invalid --set {item!r}; expected KEY=VALUE")
        overrides[key.strip()] = value
    return overrides


def _load(args: argparse.Namespace) -> AgentwatchConfig:
    overrides = _parse_overrides(args.overrides)
    return load_config(
        paths=default_paths(),
        required_paths=[Path(p) for p in args.config],
        cli_overrides=overrides,
    )


def _hooks_summary() -> str:
    installed = [
        target.scope
        for target in (resolve_scope("project"), resolve_scope("user"))
        if hooks_installed(target.settings_path)
    ]
    if installed:
        return f"hooks: installed ({'+'.join(installed)})"
    return "hooks: absent"


def _health_payload(cfg: AgentwatchConfig) -> dict[str, object]:
    """Prefer the live daemon's ``/healthz``; fall back to local truth (stopped)."""
    live = fetch_health(cfg.health.endpoint)
    if live is not None:
        return live
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    installed = any(
        hooks_installed(target.settings_path)
        for target in (resolve_scope("project"), resolve_scope("user"))
    )
    return local_snapshot(
        store=store,
        version=_version(),
        hooks_installed=installed,
        export_enabled=cfg.export.enabled,
        export_endpoint=cfg.export.otlp_endpoint,
        redaction_mode=cfg.privacy.mode,
    ).to_dict()


def _print_status(cfg: AgentwatchConfig, health: dict[str, object]) -> None:
    store = health.get("store")
    redaction = health.get("redaction")
    store_fields = store if isinstance(store, dict) else {}
    redaction_fields = redaction if isinstance(redaction, dict) else {}
    lines = [
        "agentwatch status",
        f"  state: {health.get('state')}",
        f"  state.reason: {health.get('reason') or '-'}",
        f"  store.records: {store_fields.get('records', 0)}",
        f"  store.chain_ok: {store_fields.get('chain_ok', True)}",
        f"  store.durability: {store_fields.get('durability', 'record')}",
        f"  store.size_mb: {store_fields.get('size_mb', 0.0)}",
        f"  redaction.self_test_passing: {redaction_fields.get('self_test_passing', True)}",
        f"  harness: {cfg.harness}",
        f"  mode: {cfg.mode}",
        f"  {_hooks_summary()}",
        f"  daemon: {'running' if is_daemon_alive() else 'stopped'}",
        f"  store.path: {cfg.store.path}",
        f"  store.retention_days: {cfg.store.retention_days}",
        f"  store.max_size_mb: {cfg.store.max_size_mb}",
        f"  privacy.mode: {cfg.privacy.mode}",
        f"  redaction.self_test: {cfg.redaction.self_test}",
        f"  export.enabled: {str(cfg.export.enabled).lower()}",
        f"  export.otlp_endpoint: {cfg.export.otlp_endpoint or '-'}",
        f"  export.format: {cfg.export.format}",
        f"  health.endpoint: {cfg.health.endpoint}",
        f"  log.level: {cfg.log.level}",
    ]
    lines.extend(f"  warning: {warning}" for warning in cfg.warnings)
    print("\n".join(lines))


def _run_status(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    _print_status(cfg, _health_payload(cfg))
    return 0


def _run_init(args: argparse.Namespace) -> int:
    naming.install_guard(lambda message: print(message, file=sys.stderr))
    target = resolve_scope(args.scope)
    command = resolve_hook_command()

    if args.profile:
        # Consent-first (G3): print the whole bundle before anything is written.
        print(render_profile(args.profile))
        merged = apply_profile(args.profile, _parse_overrides(args.overrides))
        args.overrides = [
            f"{key}={str(value).lower() if isinstance(value, bool) else value}"
            for key, value in merged.items()
        ]

    if args.dry_run:
        planned = {
            "settings_path": str(target.settings_path),
            "scope": target.scope,
            "hooks": {
                event: [
                    {
                        "matcher": "*",
                        "hooks": [command.handler(phase, async_hooks=not args.sync_hooks)],
                    }
                ]
                for event, phase in EVENT_PHASES.items()
            },
        }
        print(f"agentwatch: dry-run — would write {target.settings_path}")
        print(json.dumps(planned, indent=2))
        if args.mcp_proxy:
            mcp_target = resolve_mcp_scope(args.mcp_scope)
            print(f"agentwatch: dry-run — would re-point MCP config {mcp_target.path}")
            print(f"  servers: {args.mcp_servers or 'all'}")
            print(f"  http proxy: {args.mcp_host}:{args.mcp_port}")
        return 0

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    for warning in preflight(detect_claude_version()):
        print(f"agentwatch: warning: {warning}", file=sys.stderr)

    guidance = install_guidance(detect_managed_policy())
    if guidance is not None:
        print(f"agentwatch: warning: {guidance}", file=sys.stderr)

    try:
        install_hooks(target.settings_path, command, async_hooks=not args.sync_hooks)
    except InstallError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR

    # A recorder-state transition is a chain record, not a silent change (S5).
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    record_recorder_installed(store, scope=target.scope, harness=cfg.harness)
    reconcile_config(store, cfg)
    open_coverage_window(store, reason=f"init:{target.scope}")
    # DEP-2: a session-start recorder attestation (effective hook sources + a
    # keyed config digest) so recording-active is a fact, not an assumption.
    policy = detect_managed_policy()
    attest_session(
        store,
        managed=policy.managed_agentwatch,
        user=hooks_installed(resolve_scope("user").settings_path),
        project=hooks_installed(target.settings_path),
        plugin=bool(policy.force_enabled_plugins),
        managed_policy=policy.blocks_user_hooks,
    )

    print(f"agentwatch: hooks installed ({target.scope}: {target.settings_path})")
    if args.no_daemon:
        print("  daemon: not started (--no-daemon)")
    else:
        try:
            started = start_daemon()
        except InstallError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        print(f"  daemon: {'started' if started else 'already running'}")
    if args.service:
        code = _install_service()
        if code:
            return code
    if args.mcp_proxy:
        return _install_mcp_proxy(args)
    return 0


def _service_platform() -> str | None:
    return sys.platform if sys.platform in ("darwin", "linux") else None


def _install_service() -> int:
    platform = _service_platform()
    if platform is None:
        print(
            f"agentwatch: service supervision is unsupported on {sys.platform!r}",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    unit = render_unit(platform)
    path = install_service(unit)
    print(f"agentwatch: service unit written ({path})")
    if platform == "darwin":
        print(f"  load it with: launchctl load {path}")
    else:
        print("  enable it with: systemctl --user enable --now agentwatch.service")
    return 0


def _install_mcp_proxy(args: argparse.Namespace) -> int:
    """Re-point the MCP config and start the HTTP proxy when routes need one."""
    target = resolve_mcp_scope(args.mcp_scope)
    servers = (
        [name.strip() for name in args.mcp_servers.split(",") if name.strip()]
        if args.mcp_servers
        else None
    )
    try:
        report = install_mcp_proxy(
            target,
            proxy_command=resolve_mcp_proxy_command(),
            port=args.mcp_port,
            servers=servers,
            http_host=args.mcp_host,
        )
    except InstallError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR

    print(f"agentwatch: MCP config re-pointed ({target.scope}: {target.path})")
    print(f"  servers: {', '.join(report.repointed) or 'none'}")
    if report.skipped:
        print(f"  skipped (not found): {', '.join(report.skipped)}")

    if not report.http_routes:
        print("  http proxy: not needed (stdio servers only)")
        return 0
    try:
        pid = start_mcp_proxy(report.http_routes, host=args.mcp_host, port=args.mcp_port)
    except InstallError as exc:
        uninstall_mcp_proxy(target)  # roll back the config edit on a failed start
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    print(f"  http proxy: started (pid {pid}, {args.mcp_host}:{args.mcp_port})")
    return 0


def _run_uninstall(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    target = resolve_scope(args.scope)
    removed = uninstall_hooks(target.settings_path)
    stopped = stop_daemon()
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    close_coverage_window(store, reason=f"uninstall:{target.scope}")
    record_recorder_uninstalled(store, scope=target.scope, harness=cfg.harness)
    print(f"agentwatch: hooks {'removed' if removed else 'not installed'} ({target.scope})")
    print(f"  daemon: {'stopped' if stopped else 'not running'}")

    mcp_target = resolve_mcp_scope(args.mcp_scope)
    proxy_stopped = stop_mcp_proxy()
    result = uninstall_mcp_proxy(mcp_target)
    if result.restored:
        print(f"agentwatch: MCP config restored ({mcp_target.scope}: {mcp_target.path})")
    elif result.deleted:
        print(f"agentwatch: MCP config removed ({mcp_target.scope})")
    elif result.reason == "not installed":
        print(f"agentwatch: MCP config not installed ({mcp_target.scope})")
    else:
        print(f"agentwatch: MCP config not restored: {result.reason}", file=sys.stderr)
    print(f"  mcp proxy: {'stopped' if proxy_stopped else 'not running'}")
    platform = _service_platform()
    service_removed = uninstall_service(render_unit(platform)) if platform is not None else False
    print(f"  service: {'removed' if service_removed else 'not installed'}")
    return 0


def _run_mcp_proxy(args: argparse.Namespace) -> int:
    if args.http:
        from agentwatch.mcp_proxy import parse_routes, parse_transport, serve_http

        try:
            routes = parse_routes(args.route)
            transport = parse_transport(args.transport)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        if not routes:
            print("agentwatch: mcp-proxy --http requires --route NAME=URL", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        return serve_http(
            routes, host=args.host, port=args.port, socket_path=args.socket, transport=transport
        )

    from agentwatch.mcp_proxy import run_stdio

    command: list[str] = list(args.server_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command or args.server is None:
        print(
            "agentwatch: mcp-proxy requires --server NAME -- <command> [args...]",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    return run_stdio(args.server, command, socket_path=args.socket)


def _run_mcp_serve(args: argparse.Namespace) -> int:
    if not args.enable:
        print(
            "agentwatch: mcp-serve is off by default; pass --enable to opt in "
            "(read-only server over the record)",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    limiter = RateLimiter(max_queries=max(1, args.rate_limit))
    return serve_stdio(store, stdin=sys.stdin, stdout=sys.stdout, limiter=limiter)


def _run_what_if(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        policy = load_policy(args.policy_file)
    except PolicyParseError as exc:
        print(f"agentwatch: policy error: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    report = simulate_policy(store, policy, since=args.since, project=args.project)
    print(json.dumps(whatif_to_dict(report), indent=2) if args.json else render_whatif(report))
    return 0


def _run_suggest_policy(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        suggestion = suggest_policy(
            store,
            since=args.since,
            target=args.target,
            project=args.project,
            include=args.include,
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR

    if args.out is not None:
        out_path = Path(args.out).expanduser()
        if not out_path.parent.is_dir():
            print(
                f"agentwatch: --out directory does not exist: {out_path.parent}",
                file=sys.stderr,
            )
            return _EXIT_USAGE_ERROR
        out_path.write_text(
            json.dumps(suggestion_to_dict(suggestion), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"agentwatch: wrote advisory policy suggestion to {out_path}")
        return 0

    if args.json:
        print(json.dumps(suggestion_to_dict(suggestion), indent=2))
    else:
        print(render_policy_suggestion(suggestion))
    return 0


def _run_a2a_proxy(args: argparse.Namespace) -> int:
    if args.http:
        from agentwatch.a2a_proxy import parse_routes, serve_http

        try:
            routes = parse_routes(args.route)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        if not routes:
            print("agentwatch: a2a-proxy --http requires --route NAME=URL", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        return serve_http(routes, host=args.host, port=args.port, socket_path=args.socket)

    from agentwatch.a2a_proxy import run_stdio

    command: list[str] = list(args.agent_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command or args.agent is None:
        print(
            "agentwatch: a2a-proxy requires --agent NAME -- <command> [args...]",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    return run_stdio(
        args.agent, command, socket_path=args.socket, remote_org=args.remote_org
    )


def _run_archive(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_path = Path(cfg.store.path).expanduser() / "records.jsonl"
    store = RecordStore(store_path)
    try:
        report = archive_store(
            store,
            store_path,
            before=since_cutoff(args.before),
            out_dir=args.out,
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    if args.json:
        print(
            json.dumps(
                {
                    "archived": report.archived,
                    "segment_id": report.segment_id,
                    "segment_path": str(report.segment_path),
                    "anchor_seq": report.anchor_seq,
                    "remaining": report.remaining,
                }
            )
        )
        return 0
    print(
        f"agentwatch: archived {report.archived} entr(ies) into {report.segment_path} "
        f"(segment {report.segment_id}); {report.remaining} remain"
    )
    return 0


def _run_verify_store(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_path = Path(cfg.store.path).expanduser() / "records.jsonl"
    store = RecordStore(store_path)
    status = store.verify()
    if status.ok:
        print(f"agentwatch: chain ok ({status.checked} entries)")
        posture = signing_status(store, store_path.parent)
        print(f"  signing: {posture.summary}")
        broken_archive = False
        for verdict in verify_archives(store, store_path.parent):
            if verdict.ok:
                print(f"  archive {verdict.segment_id}: ok")
            elif verdict.available:
                broken_archive = True
                print(
                    f"  archive {verdict.segment_id}: BROKEN ({verdict.detail})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  archive {verdict.segment_id}: present-but-unavailable "
                    "(segment file not found)"
                )
        return _EXIT_INSTALL_ERROR if broken_archive else 0
    if not args.repair:
        print(f"agentwatch: chain broken at seq {status.broken_at}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if not args.yes:
        print("agentwatch: refusing to repair without --yes", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    report = repair_store(store_path)
    print(
        f"agentwatch: repaired store (broken at seq {report.broken_at}); "
        f"salvaged {report.salvaged}, dropped {report.dropped}"
    )
    if report.evidence_path is not None:
        print(f"  evidence: {report.evidence_path}")
    repaired = RecordStore(store_path).verify()
    return 0 if repaired.ok else _EXIT_INSTALL_ERROR


def _run_evidence(args: argparse.Namespace) -> int:
    if args.target == "verify":
        if not args.bundle:
            print("agentwatch: evidence verify needs a bundle path", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        verification = verify_bundle(args.bundle)
        print(f"agentwatch: bundle {verification.bundle_format or 'unknown'}")
        print(f"  intact    : {verification.intact}")
        print(f"  complete  : {verification.complete}")
        print(f"  leak-free : {verification.leak_free}")
        for problem in verification.problems:
            print(f"  problem: {problem}", file=sys.stderr)
        return 0 if verification.ok else _EXIT_INSTALL_ERROR

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_path = Path(cfg.store.path).expanduser() / "records.jsonl"
    store = RecordStore(store_path)
    try:
        bundle = build_bundle(
            store,
            store_path,
            args.target,
            include_bom=args.include_bom,
            redact_paths=args.redact_paths,
            includes=tuple(args.include or ()),
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    out = Path(args.out).expanduser() if args.out else Path.cwd() / f"{args.target}.evidence.zip"
    bundle.write(out)
    count = sum(1 for r in store.records() if r.session_id == args.target)
    record_store_access(
        store,
        command="evidence",
        sessions=[args.target],
        records=count,
        destination_kind=DestinationKind.BUNDLE,
    )
    print(f"agentwatch: wrote evidence bundle to {out}")
    print("  handling: may contain redacted-but-sensitive paths/arguments; treat as confidential.")
    return 0


def _run_verify_release(args: argparse.Namespace) -> int:
    report = verify_release(
        Path(args.directory),
        checksums=Path(args.checksums) if args.checksums else None,
        sbom=Path(args.sbom) if args.sbom else None,
        allow_unsigned=args.allow_unsigned,
        cosign_identity=args.cosign_identity_regexp,
        cosign_issuer=args.cosign_issuer,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for check in report.checks:
            mark = "ok " if check.ok else "FAIL"
            print(f"  [{mark}] {check.name}: {check.detail}")
        if report.ok:
            print("agentwatch: release verified")
    if report.ok:
        return 0
    failed = next((check for check in report.checks if not check.ok), None)
    reason = f"{failed.name}: {failed.detail}" if failed is not None else "unknown"
    print(f"agentwatch: invalid release: {reason}", file=sys.stderr)
    return _EXIT_INSTALL_ERROR


def _run_sessions(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    if args.group_by_behavior:
        groups = group_sessions_by_behavior(store)
        if not groups:
            print("agentwatch: no sessions recorded")
            return 0
        print(render_behavior_groups(groups))
        return 0
    if args.group_by_env:
        env_groups = group_sessions_by_env(store)
        if not env_groups:
            print("agentwatch: no sessions recorded")
            return 0
        print(render_env_groups(env_groups))
        return 0
    allowed = tagged_sessions(store, args.tag) if args.tag is not None else None
    counts: dict[str, int] = {}
    order: list[str] = []
    for record in store.records():
        if args.project is not None and record.project != args.project:
            continue
        session_id = record.session_id
        if allowed is not None and session_id not in allowed:
            continue
        if session_id not in counts:
            order.append(session_id)
            counts[session_id] = 0
        counts[session_id] += 1

    if not order:
        print("agentwatch: no sessions recorded")
        return 0
    states = session_states(store, order)
    print("SESSION\tSTATE\tRECORDS")
    for session_id in order:
        state = states[session_id].state if session_id in states else "unknown"
        print(f"{session_id}\t{state}\t{counts[session_id]}")
    return 0


def _run_tail(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    path = Path(cfg.store.path).expanduser() / "records.jsonl"
    if path.exists():
        status = RecordStore(path).verify()
        if not status.ok:
            print(
                "agentwatch: warning: hash chain broken at seq "
                f"{status.broken_at}; tailing valid records",
                file=sys.stderr,
            )

    tail = Tail(path, session_id=args.session_id, project=args.project)

    def emit(lines: Iterable[TailLine]) -> None:
        for line in lines:
            if line.is_note:
                if not args.json:
                    print(line.text)
            elif args.json:
                assert line.record is not None
                print(json.dumps(line.record.to_dict()))
            elif args.alert and line.record is not None and line.record.security_event is not None:
                print("ALERT " + line.text)
            else:
                print(line.text)

    emit(tail.read_new())
    if args.follow:
        with contextlib.suppress(KeyboardInterrupt):
            emit(follow(tail))
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    config_error: str | None = None
    cfg: AgentwatchConfig | None = None
    try:
        cfg = _load(args)
    except ConfigError as exc:
        config_error = str(exc)
    results = run_checks(cfg, config_error=config_error)
    if args.json:
        print(json.dumps(to_json(results), indent=2))
    else:
        for result in results:
            line = f"{result.status} {result.name}: {result.detail}"
            if result.hint:
                line += f"  [hint: {result.hint}]"
            print(line)
    return 0 if all_passed(results) else _EXIT_INSTALL_ERROR


def _run_event_emit(args: argparse.Namespace) -> int:
    event: dict[str, object] = {
        "event_version": EVENT_VERSION,
        "type": args.type,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "emitter": "agentwatch",
    }
    if args.tool:
        event["tool"] = args.tool
    if args.reason:
        event["reason"] = args.reason
    if args.evidence is not None:
        try:
            evidence = json.loads(args.evidence)
        except json.JSONDecodeError:
            print("agentwatch: --evidence must be a JSON object", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        if not isinstance(evidence, dict):
            print("agentwatch: --evidence must be a JSON object", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        event["evidence"] = evidence

    # Fail closed before the wire: reject-never-coerce (F8).
    try:
        validate_event(event)
    except ValueError as exc:
        print(f"agentwatch: invalid event: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    message: dict[str, object] = {"phase": "event", "harness": "agentwatch", "event": event}
    if args.session_id:
        message["session_id"] = args.session_id
    if not hook.send(message):
        print("agentwatch: daemon not reachable; event was not recorded", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    print(f"agentwatch: event emitted ({args.type})")
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    combined = combined_records(store, Path(cfg.store.path).expanduser())
    if combined.unavailable:
        print(
            "agentwatch: warning: archive(s) present-but-unavailable: "
            + ", ".join(combined.unavailable),
            file=sys.stderr,
        )
    records = (
        replay_trace(combined.records, args.session_id)
        if args.trace
        else replay_session(store, args.session_id, records=combined.records)
    )
    if not records:
        print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    seq_by_id = {
        id(entry.record): entry.seq for entry in store.entries() if entry.record is not None
    }
    if args.json:
        payload = []
        for record in records:
            item: dict[str, object] = {"record": record.to_dict()}
            if args.receipts:
                item["receipt"] = record_receipt(record, seq=seq_by_id.get(id(record), 0)).to_dict()
            payload.append(item)
        print(json.dumps(payload, indent=2))
        return 0
    for record in records:
        print(render_record(record))
        loads = capability_loads([record])
        if loads:
            print(f"    {loads[0].context_line()}")
        if args.receipts:
            receipt = record_receipt(record, seq=seq_by_id.get(id(record), 0))
            rules = ",".join(receipt.rules) if receipt.rules else "none"
            print(
                f"  receipt: kept={len(receipt.kept)} dropped={len(receipt.dropped)} rules={rules}"
            )
            for path in receipt.dropped:
                print(f"    dropped: {path}")
    if not args.json:
        from agentwatch.denials import denial_sequences, render_sequences

        sequences = denial_sequences(records)
        if sequences:
            print(render_sequences(sequences))
    return 0


def _run_redact(args: argparse.Namespace) -> int:
    if args.target == "eval":
        try:
            report = evaluate_corpus(load_corpus(args.corpus or "v1"))
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            print(render_report_table(report))
        return 0

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    mode = args.mode or cfg.privacy.mode
    if args.preview is not None:
        preview = redact_preview(args.preview, redaction_config_from_mode(mode))
        if args.json:
            print(
                json.dumps(
                    {
                        "before": preview.before,
                        "after": preview.after,
                        "rules": list(preview.rules),
                        "privacy_mode": mode,
                    }
                )
            )
            return 0
        print(f"before: {preview.before}")
        print(f"after:  {preview.after}")
        if preview.rules:
            print(f"rules:  {','.join(preview.rules)}")
        return 0

    # S13: a standalone stdin -> stdout filter. Findings go to stderr so stdout
    # stays a clean pipeline; findings name kinds and locations, never values.
    text = sys.stdin.read()
    result = redact_value(text, mode)
    sys.stdout.write("" if result.output is None else str(result.output))
    if result.findings:
        if args.json:
            print(json.dumps(findings_to_dict(result.findings)), file=sys.stderr)
        else:
            for finding in result.findings:
                print(f"redacted {finding.kind} at {finding.path}", file=sys.stderr)
    return 0


_COMMANDS_FOR_COMPLETION = (
    "init status sessions replay export verify-store verify-release "
    "verify-privacy event doctor tail "
    "completions uninstall inventory search diff view explain import ingest fleet drift retention "
    "purge export-session mcp-proxy a2a-proxy annotate redact bom evidence coverage "
    "quarantine archive "
    "impact blame cost tree trace at digest flow secrets demo config union checkpoint compliance "
    "case segment import-segment"
)


def _run_completions(args: argparse.Namespace) -> int:
    commands = _COMMANDS_FOR_COMPLETION
    if args.shell == "bash":
        script = (
            "_agentwatch_complete() {\n"
            f'  COMPREPLY=( $(compgen -W "{commands}" -- "${{COMP_WORDS[1]}}") )\n'
            "}\n"
            "complete -F _agentwatch_complete agentwatch"
        )
    elif args.shell == "zsh":
        script = f"#compdef agentwatch\n_arguments '1:command:({commands})'"
    else:
        script = f"complete -c agentwatch -f -a '{commands}'"
    print(script)
    return 0


def _run_verify_privacy(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_path = Path(cfg.store.path).expanduser() / "records.jsonl"
    verdict = verify_privacy(store_path)
    if verdict.passed:
        print(f"agentwatch: privacy ok ({verdict.checks} checks)")
        if verdict.quarantine_present:
            print("  note: quarantine holds raw frames (owner-only, never exported)")
        return 0
    print(f"agentwatch: privacy FAILED ({len(verdict.leaks)} leaks)", file=sys.stderr)
    for leak in verdict.leaks:
        print(f"  leak: {leak}", file=sys.stderr)
    return _EXIT_INSTALL_ERROR


def _run_export_session(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    export = export_session(store, args.session_id)
    if export.count == 0:
        record_store_access(
            store,
            command="export-session",
            sessions=[args.session_id],
            records=0,
            destination_kind=DestinationKind.FILE if args.output else DestinationKind.STDOUT,
            attempted=True,
            error="no records",
        )
        print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    destination = DestinationKind.FILE if args.output else DestinationKind.STDOUT
    if args.write_notes and args.format != "agent-trace":
        print(
            "agentwatch: --write-notes requires --format agent-trace",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    if args.format == "aat":
        bundle = export_aat(
            export,
            privacy_mode=cfg.privacy.mode,
            signing=signing_status(store, Path(cfg.store.path).expanduser()).to_dict(),
        )
        text = to_aat_json(bundle)
        if args.output:
            path = Path(args.output).expanduser()
            write_aat(bundle, path)
            print(f"agentwatch: exported {export.count} AAT record(s) to {path}")
        else:
            sys.stdout.write(text)
    elif args.format == "agent-trace":
        bundle = export_agent_trace(export, privacy_mode=cfg.privacy.mode)
        if args.write_notes:
            written = write_agent_trace_notes(
                str(Path(args.write_notes).expanduser()), read_agent_trace(bundle)
            )
            print(
                f"agentwatch: wrote Agent Trace notes for {written} revision(s) into "
                f"{args.write_notes}"
            )
        elif args.output:
            path = Path(args.output).expanduser()
            write_agent_trace(bundle, path)
            print(f"agentwatch: exported {export.count} Agent Trace record(s) to {path}")
        else:
            sys.stdout.write(to_agent_trace_json(bundle))
    elif args.format in ("ocsf", "cloudevents"):
        text = _render_standard_export(export, args.format)
        if args.output:
            path = Path(args.output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(
                f"agentwatch: exported {len(text.splitlines())} {args.format} object(s) to {path}"
            )
        else:
            sys.stdout.write(text)
    elif args.output:
        path = Path(args.output).expanduser()
        write_ndjson(export, path)
        print(f"agentwatch: exported {export.count} record(s) to {path}")
    else:
        sys.stdout.write(to_ndjson(export))
    record_store_access(
        store,
        command="export-session",
        sessions=[args.session_id],
        records=export.count,
        destination_kind=DestinationKind.BUNDLE if args.write_notes else destination,
    )
    return 0


def _render_standard_export(export: SessionExport, fmt: str) -> str:
    """Render a session's security events as OCSF or CloudEvents NDJSON."""
    events: list[tuple[int, SecurityEvent]] = []
    for row in export.rows:
        raw = row.get("record")
        if isinstance(raw, dict) and raw.get("security_event") is not None:
            events.append((int(row["seq"]), SecurityEvent.from_dict(raw["security_event"])))
    objects = (
        session_ocsf(events, session_id=export.session_id)
        if fmt == "ocsf"
        else session_cloudevents(events, session_id=export.session_id)
    )
    if not objects:
        return ""
    return "\n".join(json.dumps(obj, sort_keys=True, ensure_ascii=False) for obj in objects) + "\n"


def _run_view(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    if args.session_id:
        text = render_session(store, args.session_id)
        if not text:
            print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        print(text)
        return 0
    sessions = list_sessions(store)
    if not sessions:
        print("agentwatch: no sessions recorded")
        return 0
    for session_id in sessions:
        print(session_id)
    return 0


def _run_explain(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    result = explain_session(store, args.session_id)
    if result.summary.endswith("no records"):
        print(result.summary, file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    print(result.summary)
    if result.narrative is not None:
        print("\n[AI narrative]\n" + result.narrative)
    return 0


def _run_impact(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = build_impact(store, args.session_id, since=args.since)
    if report.records == 0:
        print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_impact(report))
    return 0


def _run_blame(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = build_blame(store, args.path, since=args.since, project=args.project)
    if args.sessions:
        print(blame_sessions(report))
    elif args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_blame(report))
    return 0


def _run_provenance(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    repo = args.repo or os.getcwd()
    report = build_provenance(
        store,
        args.target,
        repo=repo,
        project=args.project,
        window=args.window,
    )
    if args.notes:
        from dataclasses import replace as _replace

        ours = tuple(agent_trace_record(record) for record in store.records())
        theirs = read_agent_trace_notes(str(Path(args.notes).expanduser()))
        report = _replace(
            report, cross_validation=cross_validate(ours, theirs).to_dict()
        )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_provenance(report))
    return 0


def _run_concurrency(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = build_concurrency(store, project=args.project, since=args.since)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_concurrency(report))
    return 0


def _run_tree(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    root = build_tree(store, args.session_id)
    if args.by_cost:
        root = sort_by_cost(root)
    if args.json:
        print(json.dumps(root.to_dict(), indent=2))
    else:
        print(render_tree(root))
    return 0


def _run_trace(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    combined = combined_records(store, store_dir)
    tree = build_trace(combined.records, args.trace_id)
    if tree.records == 0:
        print(f"agentwatch: no records for trace {args.trace_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if args.json:
        print(json.dumps(trace_to_json(tree), indent=2))
    else:
        print(render_trace(tree))
    return 0


def _run_at(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = build_window(store, args.moment, window=args.window)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_window(report))
    return 0


def _run_digest(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = build_digest(store, since=args.since)
    print(render_digest(report), end="")
    return 0


def _run_flow(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    key = ensure_key_at(store_dir / "flow.key")
    records = replay_session(store, args.session_id)
    detected = detect_flows(records, key=key)
    flows: list[ContentFlow] = list(detected)
    if args.record and detected:
        record_flow_observations(store, detected)
    elif not detected:
        flows = [
            flow for flow in content_flow_observations(store) if flow.session_id == args.session_id
        ]
    if args.json:
        print(json.dumps([flow.to_dict() for flow in flows], indent=2))
    else:
        print(render_flows(args.session_id, flows))
    return 0


def _run_secrets(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    records = replay_session(store, args.session_id) if args.session_id else store.records()
    traces = trace_secrets(records)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "kind": trace.kind,
                        "fingerprint": trace.fingerprint,
                        "first_index": trace.first_index,
                        "sightings": len(trace.sightings),
                        "sinks": list(trace.sinks),
                        "verdict": trace.verdict,
                    }
                    for trace in traces
                ],
                indent=2,
            )
        )
    else:
        print(render_secrets(traces))
    return 0


def _run_demo(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    if args.purge:
        purged = purge_demo(store)
        if args.json:
            print(json.dumps({"purged": purged}))
        else:
            print(f"agentwatch demo --purge: removed {purged} demo record(s)")
        return 0
    redaction = redaction_config_from_mode(cfg.privacy.mode)
    result = run_demo(store, redaction=redaction, include_principal=cfg.privacy.include_principal)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_demo(result))
    return 0


def _run_config(args: argparse.Namespace) -> int:
    try:
        explanations = explain_config(
            key=args.key,
            cli_overrides=_parse_overrides(args.overrides),
            diff_only=args.diff,
        )
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    if args.json:
        print(json.dumps([item.to_dict() for item in explanations]))
    else:
        print(render_explanations(explanations))
    return 0


def _run_access(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    if args.action == "matrix":
        print(json.dumps(matrix_to_json()) if args.json else render_matrix())
        return 0

    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    if args.action == "log":
        entries = access_log(store, owner=args.owner)
        if args.json:
            print(json.dumps(access_log_to_json(args.owner, entries)))
        else:
            print(render_access_log(args.owner, entries))
        return 0

    reader = args.reader or args.owner
    decision = evaluate_access(
        Role(args.role),
        DataClass(args.data_class),
        owner=args.owner,
        reader=reader,
        same_team=args.same_team,
        content_available=args.content_available,
    )
    record_access_decision(store, decision)
    if args.json:
        print(json.dumps(decision.to_dict()))
    else:
        verdict = "allowed" if decision.allowed else "DENIED"
        print(f"agentwatch: access {verdict}: {decision.reason}")
    return 0 if decision.allowed else _EXIT_INSTALL_ERROR


def _run_governance(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    notice = build_notice(cfg)
    if args.json:
        print(json.dumps(notice.to_dict(), indent=2))
    else:
        print(render_notice(notice))
    return 0


def _run_hold(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")

    if args.action == "list":
        holds = active_holds(store)
        if args.json:
            print(json.dumps({"holds": [hold.to_dict() for hold in holds]}))
        else:
            print(render_holds(holds))
        return 0

    if args.action == "release":
        released = record_hold_release(store, args.hold_id, reason=args.reason)
        if released is None:
            print(f"agentwatch: no active hold {args.hold_id}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        if args.json:
            print(json.dumps({"released": released}))
        else:
            print(f"agentwatch: released hold {released}")
        return 0

    try:
        scope = parse_scope(args.scope)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    hold = record_hold_add(store, scope, reason=args.reason, ref=args.ref)
    if args.json:
        print(json.dumps(hold.to_dict()))
    else:
        ref = f" (ref {hold.ref})" if hold.ref else ""
        print(f"agentwatch: placed hold {hold.hold_id} on {hold.scope.label()}{ref}")
    return 0


def _run_case(args: argparse.Namespace) -> int:
    if args.action == "verify":
        verification = verify_case_bundle(args.bundle)
        if args.json:
            print(json.dumps(verification.to_dict()))
        else:
            print(f"agentwatch: case bundle {verification.bundle_format or 'unknown'}")
            print(f"  intact: {verification.intact}")
            for problem in verification.problems:
                print(f"  problem: {problem}", file=sys.stderr)
        return 0 if verification.ok else _EXIT_INSTALL_ERROR

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")

    if args.action == "list":
        cases = active_cases(store)
        if args.json:
            print(json.dumps({"cases": [case.to_dict() for case in cases]}))
        else:
            print(f"agentwatch case list: {len(cases)} case(s)")
            for case in cases:
                members = ",".join(member.session_id for member in case.members) or "-"
                print(f"{case.case_id}\t{case.severity}\t{case.title}\t{members}")
        return 0

    if args.action == "create":
        case = record_case_create(
            store, title=args.title, severity=args.severity, ref=args.ref
        )
        if args.json:
            print(json.dumps(case.to_dict()))
        else:
            print(f"agentwatch: created case {case.case_id} ({case.title})")
        return 0

    if args.action == "add":
        try:
            marker = record_case_add(store, args.case_id, args.session)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        if args.json:
            print(json.dumps(marker.to_dict()))
        else:
            print(f"agentwatch: added {args.session} to case {args.case_id}")
        return 0

    if args.action == "remove":
        try:
            marker = record_case_remove(store, args.case_id, args.session)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        if args.json:
            print(json.dumps(marker.to_dict()))
        else:
            print(f"agentwatch: removed {args.session} from case {args.case_id}")
        return 0

    if args.action == "export":
        try:
            bundle = build_case_bundle(store, args.case_id)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        out = Path(args.out).expanduser() if args.out else Path.cwd() / f"{args.case_id}.case.zip"
        bundle.write(out)
        if args.json:
            print(json.dumps({"case_id": bundle.case_id, "path": str(out)}))
        else:
            print(f"agentwatch: wrote case bundle to {out}")
            print("  handling: local only; no registry egress.")
        return 0

    # show
    try:
        timeline = case_timeline(store, args.case_id)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if args.json:
        print(json.dumps(timeline.to_dict()))
    else:
        print(render_case_timeline(timeline))
    return 0


def _run_import_segment(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = import_segment(store, args.bundle)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if args.json:
        print(json.dumps(report.to_dict()))
    else:
        print(
            f"agentwatch: imported segment from {report.runner} "
            f"({report.records} record(s), {len(report.sessions)} session(s))"
        )
        print("  custody: source: runner; chain-protected locally but NOT locally witnessed")
        if report.joined_sessions:
            print(f"  joined to: {', '.join(report.joined_sessions)}")
    return 0


def _run_segment(args: argparse.Namespace) -> int:
    if args.action == "verify":
        verification = verify_segment(args.bundle)
        if args.json:
            print(json.dumps(verification.to_dict()))
        else:
            print(f"agentwatch: segment {verification.bundle_format or 'unknown'}")
            print(f"  intact      : {verification.intact}")
            print(f"  attestation : {verification.attestation}")
            for problem in verification.problems:
                print(f"  problem: {problem}", file=sys.stderr)
        return 0 if verification.ok else _EXIT_INSTALL_ERROR

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")

    if args.action == "custody":
        rows = custody_rows(store)
        if args.json:
            print(
                json.dumps(
                    {
                        "anchors": [anchor.to_dict() for anchor in anchor_records(store)],
                        "rows": [row.to_dict() for row in rows],
                    }
                )
            )
        else:
            print(render_custody(store))
        return 0

    # export
    records = [record for record in store.records() if record.session_id == args.session]
    if not records:
        print(f"agentwatch: no records for session {args.session}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    started = min(record.started_at for record in records)
    ended = max(record.ended_at or record.started_at for record in records)
    try:
        segment = seal_segment(
            records,
            runner=args.runner,
            run_id=args.run_id,
            started_at=started,
            ended_at=ended,
            traceparent=args.traceparent,
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    out = (
        Path(args.out).expanduser()
        if args.out
        else Path.cwd() / f"{args.session}.segment.zip"
    )
    segment.write(out)
    if args.json:
        print(
            json.dumps(
                {"runner": segment.runner, "run_id": segment.run_id, "path": str(out)}
            )
        )
    else:
        print(f"agentwatch: wrote sealed segment to {out}")
        print("  handling: upload it yourself; agentwatch performs no egress.")
    return 0


def _run_union(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    rows = union(store, source=args.source, session_id=args.session_id)
    if args.json:
        print(json.dumps([row.to_dict() for row in rows]))
    else:
        print(render_union(rows))
    return 0


def _run_checkpoint(args: argparse.Namespace) -> int:
    if args.action == "rotate":
        try:
            cfg = _load(args)
        except ConfigError as exc:
            print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        store_dir = Path(cfg.store.path).expanduser()
        store = RecordStore(store_dir / "records.jsonl")
        try:
            result = rotate_key(store_dir / KEY_FILENAME)
        except SigningError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        seq = record_key_rotation(store, result.previous_key_id, result.key.key_id)
        if args.json:
            print(
                json.dumps(
                    {
                        "previous_key_id": result.previous_key_id,
                        "key_id": result.key.key_id,
                        "seq": seq,
                    }
                )
            )
        else:
            previous = result.previous_key_id or "(none)"
            print(
                f"agentwatch: rotated signing key {previous} -> {result.key.key_id} "
                f"(recorded at seq {seq})"
            )
        return 0
    if args.action == "verify":
        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
            export = CheckpointExport.from_dict(data)
            public_bytes = Path(args.public_key).read_bytes()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"agentwatch: cannot read checkpoint: {exc}", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
        valid = export.signature is not None and verify_checkpoint(export, public_bytes)
        if args.json:
            print(json.dumps({"ok": valid, "key_id": export.key_id, "digest": export.digest}))
        else:
            print(f"checkpoint: {'valid' if valid else 'INVALID'} (key {export.key_id})")
        return 0 if valid else 1

    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    signer = None
    if args.sign:
        try:
            signer = load_or_create_key(store_dir / KEY_FILENAME)
        except SigningError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_CONFIG_ERROR
    timestamp = (lambda digest: request_timestamp(digest, args.tsa)) if args.tsa else None
    try:
        export = export_checkpoint(store, signer=signer, timestamp=timestamp)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    text = dumps(export)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"agentwatch: checkpoint digest written to {path}")
    elif args.json:
        sys.stdout.write(text)
    else:
        print(render_checkpoint(export))
    return 0


def _run_search(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    combined = combined_records(store, Path(cfg.store.path).expanduser())
    if combined.unavailable:
        print(
            "agentwatch: warning: archive(s) present-but-unavailable: "
            + ", ".join(combined.unavailable),
            file=sys.stderr,
        )
    records = search(
        store,
        tool=args.tool,
        outcome=args.outcome,
        session_id=args.session_id,
        since=args.since,
        project=args.project,
        producer=args.producer,
        approval=args.approval,
        identity=args.identity,
        mcp_resource=args.mcp_resource,
        memory_only=args.memory,
        permission_mode=args.permission_mode,
        capability=args.capability,
        memory_store=args.memory_store,
        records=combined.records,
    )
    for record in records:
        print(json.dumps(record.to_dict()) if args.json else render_record(record))
    return 0


def _run_index(args: argparse.Namespace) -> int:
    """Manage the embedded, rebuildable query index (M30 LUI-2, ADR-0035)."""
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    index = QueryIndex(index_path_for_store(store.path))
    if args.action == "drop":
        index.drop()
        if args.json:
            print(json.dumps({"dropped": True, "path": str(index.path)}))
        else:
            print(f"agentwatch: dropped index {index.path} (chain untouched)")
        return 0
    if args.action == "export-parquet":
        index.ensure(store)
        try:
            count = index.export_parquet(args.output, session_id=args.session_id)
        except ParquetUnavailableError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        if args.json:
            print(json.dumps({"exported": count, "path": str(Path(args.output).expanduser())}))
        else:
            print(f"agentwatch: exported {count} record(s) to {args.output}")
        return 0
    status = index.rebuild(store) if args.action == "rebuild" else index.status()
    fresh = index.is_fresh(store)
    payload = {
        "path": str(status.path),
        "present": status.present,
        "fresh": fresh,
        "records": status.records,
        "format_version": status.format_version,
    }
    if args.json:
        print(json.dumps(payload))
    else:
        state = "fresh" if fresh else ("stale" if status.present else "absent")
        print(f"agentwatch: index {state} ({status.records} record(s)) at {status.path}")
    return 0


def _run_ui(args: argparse.Namespace) -> int:
    """Open the read-only loopback console (M30 LUI-1, ADR-0036)."""
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    server = ConsoleServer(store, host=args.host, port=args.port)
    server.start()
    url = f"{server.url}/?token={server.token}"
    print(f"agentwatch: console {url} (read-only, loopback only)")
    if args.check:
        try:
            request = urllib.request.Request(
                server.url + "/api/health",
                headers={"X-Agentwatch-Token": server.token},
            )
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - loopback
                health = json.loads(response.read().decode("utf-8"))
        finally:
            server.stop()
        print(f"agentwatch: readiness ok (chain_ok={health['chain_ok']})")
        return 0
    if args.open_browser:
        open_console_url(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


def _run_purge(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    if not args.yes:
        print("agentwatch: refusing to purge without --yes", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = store.purge_session(
        args.session_id,
        reason=args.reason,
        override_reason=args.override_reason,
    )
    if report.blocked_by_hold is not None:
        print(
            f"agentwatch: refusing to purge session {args.session_id}: active legal hold "
            f"{report.blocked_by_hold}; pass --override-reason with a recorded reason to proceed",
            file=sys.stderr,
        )
        return _EXIT_INSTALL_ERROR
    if not report.found:
        print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    print(f"agentwatch: purged {report.purged} record(s) for session {args.session_id}")
    if report.override_reason:
        print(f"agentwatch: legal hold override recorded: {report.override_reason}")
    if report.leftovers:
        print(
            "agentwatch: leftover derived artifact(s) may still retain data: "
            + ", ".join(report.leftovers)
        )
    return 0


def _run_annotate(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = annotate_session(
            store,
            args.session_id,
            args.note,
            tag=args.tag,
            incident_tags=args.incident_tag,
        )
    except AnnotateError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    detail = f" (tag {report.tag})" if report.tag else ""
    print(f"agentwatch: noted session {report.session_id}{detail}")
    if report.session_purged:
        print("  context: session purged")
    if report.masked_kinds:
        print(f"  note was redacted: {','.join(report.masked_kinds)}")
    return 0


def _run_retention(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(
        Path(cfg.store.path).expanduser() / "records.jsonl", max_size_mb=cfg.store.max_size_mb
    )
    profile = resolve_retention_profile(args.profile, retention_days=cfg.store.retention_days)
    previous = last_state(store).retention_days
    report = store.apply_retention(retention_days=profile.retention_days, dry_run=args.dry_run)
    # Record the policy change *after* the run so the report's counts describe the
    # records the window applied to, not the marker we add to explain it (S5).
    if not args.dry_run:
        record_retention_changed(
            store, old=previous, new=profile.retention_days, profile=profile.name
        )
    status = store.verify()
    payload: dict[str, Any] = {
        "purged": report.purged,
        "kept": report.kept,
        "chain_ok": status.ok,
        "broken_at": status.broken_at,
        "retention_days": profile.retention_days,
        "profile": profile.name,
    }
    if report.leftovers:
        payload["leftovers"] = list(report.leftovers)
    if report.held:
        payload["held"] = report.held
    if args.dry_run:
        payload["dry_run"] = True
        cutoff = datetime.now(timezone.utc) - timedelta(days=profile.retention_days)
        payload["skipped"] = [skip.to_dict() for skip in held_skips(store, cutoff)]
    if args.json:
        print(json.dumps(payload))
    else:
        print(
            f"agentwatch: retention ({profile.name}) purged {report.purged}, "
            f"kept {report.kept} ({profile.retention_days} day window)"
        )
        if report.held:
            print(f"  {report.held} record(s) skipped by an active legal hold")
        if args.dry_run:
            print("  dry run: nothing was tombstoned")
        if report.leftovers:
            print(f"  leftover derived artifact(s): {', '.join(report.leftovers)}")
        if not status.ok:
            print(f"agentwatch: chain broken at seq {status.broken_at}", file=sys.stderr)
    return 0 if status.ok else _EXIT_INSTALL_ERROR


def _run_coverage(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    cutoff = since_cutoff(args.since) if args.since else None
    if args.harness == "cursor":
        base = (
            Path(args.transcripts).expanduser()
            if args.transcripts
            else Path.home() / ".cursor" / "traces"
        )
        transcripts, present = discover_cursor_transcripts(base, since=cutoff)
        hooks_any = True
    else:
        base = (
            Path(args.transcripts).expanduser() if args.transcripts else default_transcript_base()
        )
        transcripts, present = discover_transcripts(base, since=cutoff)
        hooks_any = any(
            hooks_installed(resolve_scope(scope).settings_path) for scope in ("project", "user")
        )
    report = build_coverage(
        store,
        transcripts=transcripts,
        transcripts_present=present,
        since=args.since,
        project=args.project,
        session=args.session_id,
        hooks_installed=hooks_any,
        quarantine=QuarantineLog(store_dir / "quarantine.jsonl"),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render())
    return 0


def _run_compliance(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    report = build_report(store, args.framework, config=cfg)
    text = json.dumps(report.to_dict(), indent=2) if args.json else render_report(report)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"agentwatch: wrote compliance report to {out}", file=sys.stderr)
    else:
        print(text)
    return 0


def _run_oversight(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = build_oversight(
            store, since=args.since, project=args.project, by=args.by
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    print(json.dumps(report.to_dict(), indent=2) if args.json else render_oversight(report))
    return 0


def _run_quarantine(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    quarantine = QuarantineLog(store_dir / "quarantine.jsonl")

    if args.action == "list":
        entries = list_entries(quarantine)
        if args.json:
            print(json.dumps([entry.summary() for entry in entries], indent=2))
        else:
            if not entries:
                print("agentwatch: quarantine is empty")
                return 0
            print("ID\tAT\tREASON")
            for entry in entries:
                at = entry.at.isoformat() if entry.at else "-"
                print(f"{entry.id}\t{at}\t{entry.reason}")
        return 0

    if args.action == "inspect":
        try:
            report = inspect_entry(quarantine, store, args.entry_id, raw=args.raw)
        except QuarantineError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        if args.json:
            print(
                json.dumps(
                    {
                        **report.entry.summary(),
                        "raw": report.raw,
                        "payload": report.payload,
                        "masked_kinds": list(report.masked_kinds),
                    },
                    indent=2,
                )
            )
        else:
            entry = report.entry
            print(f"id: {entry.id}")
            print(f"at: {entry.at.isoformat() if entry.at else '-'}")
            print(f"reason: {entry.reason}")
            if report.raw:
                print("payload (raw; access recorded):")
            elif report.masked_kinds:
                print(f"payload (redacted: {','.join(report.masked_kinds)}):")
            else:
                print("payload (redacted):")
            print(report.payload)
        return 0

    if args.action == "requeue":
        from agentwatch.adapters import claude_code

        redaction = redaction_config_from_mode(cfg.privacy.mode)
        try:
            requeue_report = requeue_entries(
                quarantine,
                store,
                normalizer=lambda message: claude_code.normalize(message, redaction=redaction),
                ids=args.entry_ids,
                all_entries=args.all_entries,
            )
        except QuarantineError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_INSTALL_ERROR
        if args.json:
            print(
                json.dumps(
                    {
                        "requeued": requeue_report.requeued,
                        "records": requeue_report.records,
                        "still_failing": requeue_report.still_failing,
                        "remaining": requeue_report.remaining,
                    }
                )
            )
        else:
            print(
                f"agentwatch: requeued {requeue_report.requeued} entr(ies) into "
                f"{requeue_report.records} record(s); "
                f"{requeue_report.still_failing} still failing; "
                f"{requeue_report.remaining} remaining"
            )
        return 0

    if args.action == "clear":
        try:
            count = clear_entries(quarantine, yes=args.yes)
        except QuarantineError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        print(f"agentwatch: cleared {count} quarantined entr(ies)")
        return 0

    return _EXIT_USAGE_ERROR


def _run_cost(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = build_cost(store, by=args.by, since=args.since, per=args.per, repo=args.repo)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_cost(report))
    return 0


def _run_outcomes(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        report = build_outcomes(
            store, by=args.by, since=args.since, repo=args.repo
        )
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_outcomes(report))
    return 0


def _run_inventory(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    if args.memory:
        project = Path(args.project).expanduser() if args.project else Path.cwd()
        stores = discover_memory_stores(project=project, home=Path.home())
        if args.json:
            print(json.dumps([store.to_dict() for store in stores], indent=2))
        else:
            print(render_memory_stores(stores))
        return 0
    if args.capabilities:
        if args.diff:
            cutoff = since_cutoff(args.since) if args.since else None
            changes = detect_capability_changes(store.records(), since=cutoff)
            if args.json:
                print(json.dumps([change.to_dict() for change in changes]))
            else:
                print(render_capability_changes(changes))
            return 0
        project = Path(args.project).expanduser() if args.project else Path.cwd()
        inventory = discover_capabilities(project=project, home=Path.home())
        if args.snapshot:
            session_id = args.session_id or "inventory"
            changes = record_capability_snapshot(store, session_id, inventory.capabilities)
            message = f"recorded {len(inventory.capabilities)} capabilities in {session_id}"
            if args.json:
                print(json.dumps({"recorded": len(inventory.capabilities),
                                  "changes": [change.to_dict() for change in changes]}))
            else:
                print(message)
            return 0
        if args.json:
            print(json.dumps(capabilities_to_json(inventory), indent=2))
        else:
            print(render_capabilities(inventory))
        return 0
    if args.snapshot or args.diff:
        records = store.records()
        if args.snapshot:
            states = [
                state
                for state in survey(records)
                if args.server is None or state.server == args.server
            ]
            if args.json:
                print(json.dumps([state.to_dict() for state in states]))
            else:
                print(render_snapshots(states))
        else:
            changes = detect_surface_changes(records, server=args.server)
            if args.json:
                print(json.dumps([change.to_dict() for change in changes]))
            else:
                print(render_changes(changes))
        return 0
    inventory = build_inventory(store, session_id=args.session_id, project=args.project)
    if args.json:
        print(json.dumps(inventory_to_json(inventory)))
    else:
        print(render_inventory(inventory))
    return 0


def _run_bom(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    capabilities = discover_capabilities(project=Path.cwd(), home=Path.home()).capabilities
    bom = build_bom(
        store, session_id=args.session_id, project=args.project, capabilities=capabilities
    )
    document = to_cyclonedx(bom) if args.format == "cyclonedx" else to_agentwatch_json(bom)
    print(json.dumps(document, indent=2, sort_keys=True))
    record_store_access(
        store,
        command="bom",
        sessions=list(bom.coverage.sessions),
        records=bom.coverage.records,
        destination_kind=DestinationKind.STDOUT,
    )
    return 0


def _run_diff(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    result = diff_sessions(store, args.a, args.b)
    if args.json:
        print(
            json.dumps(
                {
                    "a": result.a,
                    "b": result.b,
                    "records_a": result.records_a,
                    "records_b": result.records_b,
                    "failed_a": result.failed_a,
                    "failed_b": result.failed_b,
                    "added_tools": list(result.added_tools),
                    "removed_tools": list(result.removed_tools),
                    "state_a": result.state_a,
                    "state_b": result.state_b,
                    "environment_a": result.environment_a.to_dict(),
                    "environment_b": result.environment_b.to_dict(),
                    "environment_changes": [
                        change.to_dict() for change in result.environment_changes
                    ],
                }
            )
        )
    else:
        print(result.render())
    return 0


def _run_import(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    paths = resolve_paths(Path(args.path).expanduser())
    if not paths:
        print("agentwatch: no transcripts found", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    redaction = redaction_config_from_mode(args.capture)
    stats = import_transcripts(paths, store, redaction=redaction)
    if args.json:
        print(
            json.dumps(
                {
                    "files": stats.files,
                    "records": stats.records,
                    "skipped": stats.skipped,
                    "duplicates": stats.duplicates,
                }
            )
        )
    else:
        print(
            f"imported {stats.records} records from {stats.files} file(s); "
            f"{stats.skipped} skipped; {stats.duplicates} already present"
        )
    return 0


def _run_ingest(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store_dir = Path(cfg.store.path).expanduser()
    store = RecordStore(store_dir / "records.jsonl")
    redaction = redaction_config_from_mode(args.capture)
    if args.agent == "opencode":
        from agentwatch.opencode_reader import ingest_storage

        opencode_stats = ingest_storage(Path(args.path).expanduser(), store, redaction=redaction)
        if args.json:
            print(
                json.dumps(
                    {
                        "records": opencode_stats.records,
                        "sessions": opencode_stats.sessions,
                        "skipped": opencode_stats.skipped,
                        "duplicates": opencode_stats.duplicates,
                        "dangling": opencode_stats.dangling,
                    }
                )
            )
        else:
            print(
                f"ingested {opencode_stats.records} records from {opencode_stats.sessions} "
                f"session(s); {opencode_stats.skipped} skipped; "
                f"{opencode_stats.duplicates} duplicate(s); {opencode_stats.dangling} dangling"
            )
        return 0
    paths = resolve_ingest_paths(Path(args.path).expanduser())
    if not paths:
        print("agentwatch: no sources found", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    if args.agent == "codex":
        from agentwatch.codex_rollout import ingest_rollouts

        rollout_stats = ingest_rollouts(paths, store, redaction=redaction)
        if args.json:
            print(
                json.dumps(
                    {
                        "files": rollout_stats.files,
                        "records": rollout_stats.records,
                        "skipped": rollout_stats.skipped,
                        "duplicates": rollout_stats.duplicates,
                        "dangling": rollout_stats.dangling,
                    }
                )
            )
        else:
            print(
                f"ingested {rollout_stats.records} records from {rollout_stats.files} file(s); "
                f"{rollout_stats.skipped} skipped; {rollout_stats.duplicates} duplicate(s); "
                f"{rollout_stats.dangling} dangling session(s)"
            )
        return 0
    if args.format == "claude-compliance":
        return _run_ingest_claude_compliance(args, store, paths, redaction)
    if args.format == "system-ingest":
        return _run_ingest_system(args, store, store_dir, paths, redaction)
    stats = run_ingest(
        paths,
        store,
        fmt=args.format,
        quarantine=QuarantineLog(store_dir / "quarantine.jsonl"),
        redaction=redaction,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "files": stats.files,
                    "records": stats.records,
                    "skipped": stats.skipped,
                    "duplicates": stats.duplicates,
                    "problems": [{"source": p.source, "reason": p.reason} for p in stats.problems],
                }
            )
        )
    else:
        print(
            f"ingested {stats.records} records from {stats.files} file(s); "
            f"{stats.skipped} skipped; {stats.duplicates} already present; "
            f"{len(stats.problems)} problem(s)"
        )
    return 0


def _run_ingest_system(
    args: argparse.Namespace,
    store: RecordStore,
    store_dir: Path,
    paths: list[Path],
    redaction: Any,
) -> int:
    """Opt-in Linux system-effects ingest (M29 SYS-1)."""
    from agentwatch.quarantine import QuarantineLog
    from agentwatch.system_ingest import SessionIndex, run_system_ingest

    if not args.consent:
        print(
            "agentwatch: --format system-ingest is Linux-only and requires --consent",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    sessions = SessionIndex.from_records(store.records())
    stats = run_system_ingest(
        paths,
        store,
        opted_in=True,
        sessions=sessions,
        quarantine=QuarantineLog(store_dir / "quarantine.jsonl"),
        redaction=redaction,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "files": stats.files,
                    "records": stats.records,
                    "skipped": stats.skipped,
                    "duplicates": stats.duplicates,
                    "problems": [
                        {"source": p.source, "reason": p.reason} for p in stats.problems
                    ],
                }
            )
        )
    else:
        print(
            f"ingested {stats.records} system record(s) from {stats.files} file(s); "
            f"{stats.skipped} skipped; {stats.duplicates} already present; "
            f"{len(stats.problems)} problem(s)"
        )
    return 0


def _run_ingest_claude_compliance(
    args: argparse.Namespace,
    store: RecordStore,
    paths: list[Path],
    redaction: Any,
) -> int:
    """Consent-first Claude Compliance API ingest (M27 CCA-1)."""
    from agentwatch.compliance_api import classify_discrepancies, read_compliance_export
    from agentwatch.store_access import DestinationKind, record_store_access

    if not args.consent:
        print(
            "agentwatch: --format claude-compliance requires explicit --consent",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR
    record_store_access(
        store, command="claude-compliance", destination_kind=DestinationKind.COMPLIANCE_API
    )
    feed: list[Any] = []
    skipped = 0
    problems: list[dict[str, str]] = []
    for path in paths:
        try:
            read = read_compliance_export(path, redaction=redaction)
        except (OSError, ValueError) as exc:
            problems.append({"source": path.name, "reason": str(exc)})
            skipped += 1
            continue
        feed.extend(read.records)
        skipped += read.skipped
    observations, notes = classify_discrepancies(feed, store)
    appended = 0
    for record in [*feed, *observations]:
        try:
            store.append(record)
        except ValueError:
            skipped += 1
        else:
            appended += 1
    if args.json:
        print(
            json.dumps(
                {
                    "records": appended,
                    "skipped": skipped,
                    "discrepancies": notes,
                    "problems": problems,
                }
            )
        )
    else:
        print(
            f"ingested {appended} compliance record(s); {skipped} skipped; "
            f"{len(notes)} discrepancy(ies)"
        )
        for note in notes:
            print(f"  discrepancy: {note}")
    return 0


def _run_drift(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    try:
        samples = metric_series(store.records(), args.metric, bucket=args.bucket)
    except ValueError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_USAGE_ERROR

    signals = detect_drift(
        args.metric,
        samples,
        window=args.window,
        z_threshold=args.z_threshold,
        min_samples=args.min_samples,
    )
    deployments = load_deployments(Path(args.deploys).expanduser()) if args.deploys else []
    correlated = correlate_deployments(signals, deployments, window_seconds=args.deploy_window)
    emitted = emit_signals(signals) if args.emit else 0
    dated_env = environment_changes(session_environments(store))

    if args.json:
        print(
            json.dumps(
                {
                    "metric": args.metric,
                    "samples": len(samples),
                    "signals": [
                        {
                            **signal_to_json(item.signal),
                            "deployments": [deployment.label for deployment in item.deployments],
                            "environment_coincides": [
                                change.to_dict()
                                for change in annotate_environment(
                                    signal_at=item.signal.at,
                                    changes=dated_env,
                                    window_seconds=args.deploy_window,
                                )
                            ],
                        }
                        for item in correlated
                    ],
                }
            )
        )
        return 0

    print(f"agentwatch: drift {args.metric}: {len(samples)} sample(s), {len(signals)} signal(s)")
    for item in correlated:
        signal = item.signal
        print(
            f"  {signal.direction} z={signal.z_score:.2f} value={signal.value} "
            f"baseline={signal.baseline_mean:.2f}+/-{signal.baseline_stdev:.2f} "
            f"at {signal.at.isoformat()}"
        )
        for deployment in item.deployments:
            suffix = f" {deployment.version}" if deployment.version else ""
            print(f"    deploy: {deployment.label}{suffix} at {deployment.at.isoformat()}")
        for change in annotate_environment(
            signal_at=signal.at, changes=dated_env, window_seconds=args.deploy_window
        ):
            print(
                f"    coincides with environment change: "
                f"{change.field} {change.a} -> {change.b}"
            )
    if args.emit:
        print(f"  emitted {emitted} drift-detected event(s)")
    return 0


def _run_fleet(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")

    if args.action == "ingest":
        try:
            sources = parse_sources(args.sources)
        except ValueError as exc:
            print(f"agentwatch: {exc}", file=sys.stderr)
            return _EXIT_USAGE_ERROR
        for source in sources:
            stats = ingest_host(source, store)
            if stats.missing:
                print(
                    f"agentwatch: host {source.host}: no store at {source.records_path}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"agentwatch: host {source.host}: ingested {stats.records} record(s); "
                    f"{stats.duplicates} already present; {stats.skipped} skipped"
                )
        return 0

    snapshot = build_fleet(store, group_by_host=not args.no_group_by_host)
    print(json.dumps(fleet_to_json(snapshot)) if args.json else render_fleet(snapshot))
    return 0


def _run_deferred(command: str) -> int:
    print(
        f"agentwatch: '{command}' is not implemented in v0.1.0; see the WBS for its milestone.",
        file=sys.stderr,
    )
    return _EXIT_NOT_IMPLEMENTED


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch a parsed command and return a process exit code."""
    if args.command == "status":
        return _run_status(args)
    if args.command == "config":
        return _run_config(args)
    if args.command == "access":
        return _run_access(args)
    if args.command == "governance":
        return _run_governance(args)
    if args.command == "hold":
        return _run_hold(args)
    if args.command == "case":
        return _run_case(args)
    if args.command == "segment":
        return _run_segment(args)
    if args.command == "import-segment":
        return _run_import_segment(args)
    if args.command == "union":
        return _run_union(args)
    if args.command == "checkpoint":
        return _run_checkpoint(args)
    if args.command == "init":
        return _run_init(args)
    if args.command == "uninstall":
        return _run_uninstall(args)
    if args.command == "mcp-proxy":
        return _run_mcp_proxy(args)
    if args.command == "mcp-serve":
        return _run_mcp_serve(args)
    if args.command == "suggest-policy":
        return _run_suggest_policy(args)
    if args.command == "what-if":
        return _run_what_if(args)
    if args.command == "a2a-proxy":
        return _run_a2a_proxy(args)
    if args.command == "sessions":
        return _run_sessions(args)
    if args.command == "verify-store":
        return _run_verify_store(args)
    if args.command == "archive":
        return _run_archive(args)
    if args.command == "evidence":
        return _run_evidence(args)
    if args.command == "verify-release":
        return _run_verify_release(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "tail":
        return _run_tail(args)
    if args.command == "event":
        return _run_event_emit(args)
    if args.command == "replay":
        return _run_replay(args)
    if args.command == "redact":
        return _run_redact(args)
    if args.command == "verify-privacy":
        return _run_verify_privacy(args)
    if args.command == "completions":
        return _run_completions(args)
    if args.command == "export-session":
        return _run_export_session(args)
    if args.command == "view":
        return _run_view(args)
    if args.command == "explain":
        return _run_explain(args)
    if args.command == "impact":
        return _run_impact(args)
    if args.command == "blame":
        return _run_blame(args)
    if args.command == "provenance":
        return _run_provenance(args)
    if args.command == "concurrency":
        return _run_concurrency(args)
    if args.command == "tree":
        return _run_tree(args)
    if args.command == "trace":
        return _run_trace(args)
    if args.command == "at":
        return _run_at(args)
    if args.command == "digest":
        return _run_digest(args)
    if args.command == "flow":
        return _run_flow(args)
    if args.command == "secrets":
        return _run_secrets(args)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "search":
        return _run_search(args)
    if args.command == "index":
        return _run_index(args)
    if args.command == "ui":
        return _run_ui(args)
    if args.command == "diff":
        return _run_diff(args)
    if args.command == "import":
        return _run_import(args)
    if args.command == "ingest":
        return _run_ingest(args)
    if args.command == "fleet":
        return _run_fleet(args)
    if args.command == "drift":
        return _run_drift(args)
    if args.command == "inventory":
        return _run_inventory(args)
    if args.command == "cost":
        return _run_cost(args)
    if args.command == "outcomes":
        return _run_outcomes(args)
    if args.command == "coverage":
        return _run_coverage(args)
    if args.command == "compliance":
        return _run_compliance(args)
    if args.command == "oversight":
        return _run_oversight(args)
    if args.command == "bom":
        return _run_bom(args)
    if args.command == "retention":
        return _run_retention(args)
    if args.command == "purge":
        return _run_purge(args)
    if args.command == "quarantine":
        return _run_quarantine(args)
    if args.command == "annotate":
        return _run_annotate(args)
    return _run_deferred(str(args.command))


def subcommands() -> list[str]:
    """The registered subcommand names (used by the error-contract test)."""
    parser = _build_parser()
    for action in parser._actions:  # noqa: SLF001 - argparse exposes no public accessor
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    return []


def _captured_message(captured: str) -> str:
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    if not lines:
        return ""
    line = lines[-1]
    if line.startswith("agentwatch"):
        _, sep, rest = line.partition(": ")
        if sep:
            line = rest
    return line.strip()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code.

    Every failure path emits exactly one machine-readable error envelope on
    stderr (PRD 38 §Q8). Human-facing output is preserved ahead of the envelope,
    and the process exit status comes from the error catalog.
    """
    parser = _build_parser()
    captured = io.StringIO()
    code = 0
    error: errors.AgentwatchError | None = None
    usage_exit: SystemExit | None = None
    try:
        with contextlib.redirect_stderr(captured):
            args = parser.parse_args(argv)
            code = _dispatch(args)
    except errors.AgentwatchError as exc:
        code = errors.exit_code(exc.code)
        error = exc
    except SystemExit as exc:  # argparse --help/--version (0) or a usage error
        usage_exit = exc
        code = int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 - the contract catches unexpected failures
        if os.environ.get("AGENTWATCH_DEBUG"):
            raise
        error = errors.AgentwatchError(errors.ErrorCode.INTERNAL, str(exc))
        code = errors.exit_code(error.code)

    human = captured.getvalue()
    if human:
        sys.stderr.write(human)

    if code != 0:
        if error is not None:
            errors.emit(error.code, error.message, error.hint)
        else:
            message = _captured_message(human)
            errors.emit(errors.classify(code, message), message)

    if usage_exit is not None:
        raise usage_exit
    return code
