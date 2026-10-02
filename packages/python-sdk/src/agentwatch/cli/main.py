"""agentwatch command-line entry point (issue #11).

M1 wires the framework and every documented subcommand so ``agentwatch --help``
lists them. ``status`` is fully implemented; the daemon/store/hook subcommands
land in M3-M5 and fail closed here rather than pretending to succeed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from agentwatch.configuration import AgentwatchConfig, ConfigError, default_paths, load_config

# Documented subcommands ([cli-reference](../../../../docs/reference/cli-reference.md)).
DEFERRED_COMMANDS = ("init", "sessions", "replay", "export", "verify-store", "migrate", "uninstall")

_EXIT_CONFIG_ERROR = 2
_EXIT_NOT_IMPLEMENTED = 3


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
        help="extra config file (highest file precedence; repeatable)",
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

    sub.add_parser("init", help="install hooks + start the daemon (M3)")
    sub.add_parser("status", help="print the resolved configuration / health summary")
    sub.add_parser("sessions", help="list recorded sessions (M3)")

    replay = sub.add_parser("replay", help="reconstruct a session timeline (M5)")
    replay.add_argument("session_id", help="session id to replay")

    export = sub.add_parser("export", help="opt-in OTLP export (M5)")
    export_sub = export.add_subparsers(dest="action", metavar="ACTION", required=True)
    export_sub.add_parser("enable", help="enable export")
    export_sub.add_parser("disable", help="disable export")

    sub.add_parser("verify-store", help="check the store hash chain (M4)")
    migrate = sub.add_parser("migrate", help="store-format migration (M9+)")
    migrate.add_argument("--rollback", action="store_true", help="roll back the last migration")
    sub.add_parser("uninstall", help="remove hooks and stop the daemon (M3)")

    return parser


def _parse_overrides(items: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise ConfigError(f"invalid --set {item!r}; expected KEY=VALUE")
        overrides[key.strip()] = value
    return overrides


def _print_status(cfg: AgentwatchConfig) -> None:
    lines = [
        "agentwatch status",
        f"  harness: {cfg.harness}",
        f"  mode: {cfg.mode}",
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
        paths = default_paths() + [Path(p) for p in args.config]
        overrides = _parse_overrides(args.overrides)
        cfg = load_config(paths=paths, cli_overrides=overrides)
    except ConfigError as exc:
        print(f"agentwatch: configuration error: {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR
    _print_status(cfg)
    return 0


def _run_deferred(command: str) -> int:
    print(
        f"agentwatch: '{command}' is not implemented in v0.1.0 M1; "
        "see the WBS for its milestone.",
        file=sys.stderr,
    )
    return _EXIT_NOT_IMPLEMENTED


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _build_parser().parse_args(argv)
    if args.command == "status":
        return _run_status(args)
    return _run_deferred(str(args.command))
