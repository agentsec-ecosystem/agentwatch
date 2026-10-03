"""agentwatch command-line entry point (issue #11).

M1 wired the framework and every documented subcommand so ``agentwatch --help``
lists them. ``status`` is fully implemented; M3 adds ``init``/``uninstall``
(hook installation + daemon lifecycle) and ``sessions``. Remaining commands
land in M4-M5 and fail closed here rather than pretending to succeed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from agentwatch import hook
from agentwatch.configuration import AgentwatchConfig, ConfigError, default_paths, load_config
from agentwatch.doctor import all_passed, run_checks, to_json
from agentwatch.explain import explain_session
from agentwatch.health import fetch_health, local_snapshot
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
    stop_daemon,
    uninstall_hooks,
)
from agentwatch.records import EVENT_VERSION, SecurityEventType, validate_event
from agentwatch.replay import replay_session
from agentwatch.store import RecordStore
from agentwatch.tail import Tail, TailLine, follow, render_record
from agentwatch.verify_privacy import verify_privacy
from agentwatch.view import list_sessions, render_session

# Documented subcommands still deferred to a later milestone
# ([cli-reference](../../../../docs/reference/cli-reference.md)).
DEFERRED_COMMANDS = ("replay", "export", "migrate")

_EXIT_CONFIG_ERROR = 2
_EXIT_INSTALL_ERROR = 1
_EXIT_NOT_IMPLEMENTED = 3
_EXIT_USAGE_ERROR = 2


def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib always present on 3.10+
        return "0.1.0"
    try:
        return version("agentwatch")
    except PackageNotFoundError:  # pragma: no cover - editable/source checkout
        return "0.1.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentwatch",
        description="Local-first execution observability for AI agents.",
    )
    parser.add_argument("--version", action="version", version=f"agentwatch {_version()}")
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

    sub.add_parser("status", help="print the resolved configuration / health summary")
    sub.add_parser("sessions", help="list recorded sessions (M3)")
    sub.add_parser("verify-privacy", help="verify redaction and scan the store for leaks (M5)")
    completions = sub.add_parser("completions", help="print a shell completion script (M5)")
    completions.add_argument("shell", choices=("bash", "zsh", "fish"))

    doctor = sub.add_parser(
        "doctor", help="run an ordered health checklist with fix hints (M5)"
    )
    doctor.add_argument("--json", action="store_true", help="emit the checklist as JSON")

    tail = sub.add_parser("tail", help="print a read-only stream of records (M5)")
    tail.add_argument("-f", "--follow", action="store_true", help="follow new records (1 s poll)")
    tail.add_argument("--session-id", default=None, help="only show records for this session")
    tail.add_argument("--json", action="store_true", help="emit one JSON object per record")

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

    view = sub.add_parser("view", help="terminal timeline of a session (M7)")
    view.add_argument(
        "session_id", nargs="?", default=None, help="session id (omit to list sessions)"
    )

    explain = sub.add_parser("explain", help="summarize a session (deterministic, local-first)")
    explain.add_argument("session_id", help="session id to summarize")

    export = sub.add_parser("export", help="opt-in OTLP export (M5)")
    export_sub = export.add_subparsers(dest="action", metavar="ACTION", required=True)
    export_sub.add_parser("enable", help="enable export")
    export_sub.add_parser("disable", help="disable export")

    sub.add_parser("verify-store", help="check the store hash chain (M4)")
    migrate = sub.add_parser("migrate", help="store-format migration (M9+)")
    migrate.add_argument("--rollback", action="store_true", help="roll back the last migration")

    uninstall = sub.add_parser("uninstall", help="remove hooks and stop the daemon (M3)")
    uninstall.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="which hooks to remove (default: project)",
    )

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
    target = resolve_scope(args.scope)
    command = resolve_hook_command()

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
        return 0

    try:
        _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    for warning in preflight(detect_claude_version()):
        print(f"agentwatch: warning: {warning}", file=sys.stderr)

    try:
        install_hooks(target.settings_path, command, async_hooks=not args.sync_hooks)
    except InstallError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR

    print(f"agentwatch: hooks installed ({target.scope}: {target.settings_path})")
    if args.no_daemon:
        print("  daemon: not started (--no-daemon)")
        return 0
    try:
        started = start_daemon()
    except InstallError as exc:
        print(f"agentwatch: {exc}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    print(f"  daemon: {'started' if started else 'already running'}")
    return 0


def _run_uninstall(args: argparse.Namespace) -> int:
    try:
        _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    target = resolve_scope(args.scope)
    removed = uninstall_hooks(target.settings_path)
    stopped = stop_daemon()
    print(f"agentwatch: hooks {'removed' if removed else 'not installed'} ({target.scope})")
    print(f"  daemon: {'stopped' if stopped else 'not running'}")
    return 0


def _run_verify_store(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    status = store.verify()
    if status.ok:
        print(f"agentwatch: chain ok ({status.checked} entries)")
        return 0
    print(f"agentwatch: chain broken at seq {status.broken_at}", file=sys.stderr)
    return _EXIT_INSTALL_ERROR


def _run_sessions(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    store = RecordStore(Path(cfg.store.path).expanduser() / "records.jsonl")
    counts: dict[str, int] = {}
    order: list[str] = []
    for record in store.records():
        session_id = record.session_id
        if session_id not in counts:
            order.append(session_id)
            counts[session_id] = 0
        counts[session_id] += 1

    if not order:
        print("agentwatch: no sessions recorded")
        return 0
    print("SESSION\tRECORDS")
    for session_id in order:
        print(f"{session_id}\t{counts[session_id]}")
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

    tail = Tail(path, session_id=args.session_id)

    def emit(lines: Iterable[TailLine]) -> None:
        for line in lines:
            if line.is_note:
                if not args.json:
                    print(line.text)
            elif args.json:
                assert line.record is not None
                print(json.dumps(line.record.to_dict()))
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
    records = replay_session(store, args.session_id)
    if not records:
        print(f"agentwatch: no records for session {args.session_id}", file=sys.stderr)
        return _EXIT_INSTALL_ERROR
    for record in records:
        print(render_record(record))
    return 0


_COMMANDS_FOR_COMPLETION = (
    "init status sessions replay export verify-store verify-privacy event doctor tail "
    "completions uninstall"
)


def _run_completions(args: argparse.Namespace) -> int:
    commands = _COMMANDS_FOR_COMPLETION
    if args.shell == "bash":
        script = (
            "_agentwatch_complete() {\n"
            f"  COMPREPLY=( $(compgen -W \"{commands}\" -- \"${{COMP_WORDS[1]}}\") )\n"
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


def _run_deferred(command: str) -> int:
    print(
        f"agentwatch: '{command}' is not implemented in v0.1.0; "
        "see the WBS for its milestone.",
        file=sys.stderr,
    )
    return _EXIT_NOT_IMPLEMENTED


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    if args.command == "status":
        return _run_status(args)
    if args.command == "init":
        return _run_init(args)
    if args.command == "uninstall":
        return _run_uninstall(args)
    if args.command == "sessions":
        return _run_sessions(args)
    if args.command == "verify-store":
        return _run_verify_store(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "tail":
        return _run_tail(args)
    if args.command == "event":
        return _run_event_emit(args)
    if args.command == "replay":
        return _run_replay(args)
    if args.command == "verify-privacy":
        return _run_verify_privacy(args)
    if args.command == "completions":
        return _run_completions(args)
    if args.command == "view":
        return _run_view(args)
    if args.command == "explain":
        return _run_explain(args)
    return _run_deferred(str(args.command))
