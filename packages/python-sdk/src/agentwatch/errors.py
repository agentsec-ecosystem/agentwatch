"""One machine-readable error contract (PRD 38 §Q8, issue #225).

Every CLI failure — usage, configuration, a broken chain, a missing session, an
unimplemented command, or an unexpected crash — emits exactly one JSON envelope
on stderr::

    {"error": {"code": "E_CONFIG", "message": "...", "hint": "...", "doc_url": "..."}}

The catalog below is the single source of truth for codes, their process exit
codes, and their documentation URL. The exit-code table in
``docs/reference/errors.md`` is **generated** from this catalog (checked in CI by
``tests/test_error_contract.py``), never hand-maintained.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any


class ErrorCode:
    """Stable, machine-readable error codes. Do not renumber; add only."""

    USAGE = "E_USAGE"
    CONFIG = "E_CONFIG"
    INSTALL = "E_INSTALL"
    NOT_IMPLEMENTED = "E_NOT_IMPLEMENTED"
    CHAIN_BROKEN = "E_CHAIN_BROKEN"
    SESSION_NOT_FOUND = "E_SESSION_NOT_FOUND"
    DAEMON_UNREACHABLE = "E_DAEMON_UNREACHABLE"
    CONFIRMATION_REQUIRED = "E_CONFIRMATION_REQUIRED"
    NO_TRANSCRIPTS = "E_NO_TRANSCRIPTS"
    NO_SOURCES = "E_NO_SOURCES"
    INVALID_INPUT = "E_INVALID_INPUT"
    FAILED = "E_FAILED"
    INTERNAL = "E_INTERNAL"


@dataclass(frozen=True)
class ErrorSpec:
    """A code, its process exit status, and its human-facing metadata."""

    code: str
    exit_code: int
    summary: str
    hint: str


# Order defines the published table order; the catch-alls come last.
CATALOG: tuple[ErrorSpec, ...] = (
    ErrorSpec(
        ErrorCode.USAGE,
        2,
        "Bad arguments or an unknown subcommand/flag (argparse usage error).",
        "Run `agentwatch <command> --help` and re-run.",
    ),
    ErrorSpec(
        ErrorCode.CONFIG,
        2,
        "Configuration is invalid, unknown, or missing an explicit `--config` file (fail-closed).",
        "Fix or remove the reported key/value; configuration is strict.",
    ),
    ErrorSpec(
        ErrorCode.INSTALL,
        1,
        "install/hook/daemon lifecycle failed, or a check ran and failed.",
        "Run `agentwatch doctor` for the failing check.",
    ),
    ErrorSpec(
        ErrorCode.NOT_IMPLEMENTED,
        3,
        "The subcommand is wired but not implemented in this milestone.",
        "See the WBS for the milestone that lands it.",
    ),
    ErrorSpec(
        ErrorCode.CHAIN_BROKEN,
        1,
        "The store hash chain did not verify.",
        "Run `agentwatch sessions --check` or `agentwatch verify-store` for the break.",
    ),
    ErrorSpec(
        ErrorCode.SESSION_NOT_FOUND,
        1,
        "No records exist for the requested session.",
        "Run `agentwatch sessions` to list recorded sessions.",
    ),
    ErrorSpec(
        ErrorCode.DAEMON_UNREACHABLE,
        1,
        "The daemon could not be reached.",
        "Run `agentwatch init` or `agentwatch status` to check the daemon.",
    ),
    ErrorSpec(
        ErrorCode.CONFIRMATION_REQUIRED,
        1,
        "A destructive action was refused without confirmation.",
        "Re-run with `--yes` if the action is intended.",
    ),
    ErrorSpec(
        ErrorCode.NO_TRANSCRIPTS,
        1,
        "No transcripts were found to import.",
        "Pass an explicit path or check the source directory.",
    ),
    ErrorSpec(
        ErrorCode.NO_SOURCES,
        1,
        "No sources were found to ingest.",
        "Pass an explicit path or check the source directory.",
    ),
    ErrorSpec(
        ErrorCode.INVALID_INPUT,
        1,
        "Input (a record, event, or option value) was invalid.",
        "Check the reported field and retry.",
    ),
    ErrorSpec(
        ErrorCode.FAILED,
        1,
        "The command failed without a more specific code.",
        "Re-run with more context or check the message.",
    ),
    ErrorSpec(
        ErrorCode.INTERNAL,
        1,
        "An unexpected internal error occurred.",
        "Re-run; if it persists, report it with the command and message.",
    ),
)

_BY_CODE: dict[str, ErrorSpec] = {spec.code: spec for spec in CATALOG}

DOC_BASE = "https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/reference/errors.md"


def doc_url(code: str) -> str:
    """The canonical documentation URL for ``code``."""
    return f"{DOC_BASE}#{code.lower().replace('_', '-')}"


def exit_code(code: str) -> int:
    """The process exit status for ``code`` (``E_FAILED`` when unknown)."""
    spec = _BY_CODE.get(code)
    return spec.exit_code if spec is not None else _BY_CODE[ErrorCode.FAILED].exit_code


def spec_for(code: str) -> ErrorSpec:
    return _BY_CODE.get(code, _BY_CODE[ErrorCode.FAILED])


class AgentwatchError(Exception):
    """An error carrying a stable code. Raised where a specific code is known."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def envelope(code: str, message: str, hint: str | None = None) -> dict[str, Any]:
    """Build the machine-readable error envelope."""
    spec = spec_for(code)
    return {
        "error": {
            "code": spec.code,
            "message": message or spec.summary,
            "hint": hint or spec.hint,
            "doc_url": doc_url(spec.code),
        }
    }


_HINTS: tuple[tuple[str, str], ...] = (
    ("chain broken", ErrorCode.CHAIN_BROKEN),
    ("no records for session", ErrorCode.SESSION_NOT_FOUND),
    ("daemon not reachable", ErrorCode.DAEMON_UNREACHABLE),
    ("refusing to", ErrorCode.CONFIRMATION_REQUIRED),
    ("no transcripts found", ErrorCode.NO_TRANSCRIPTS),
    ("no sources found", ErrorCode.NO_SOURCES),
    ("invalid", ErrorCode.INVALID_INPUT),
)


def classify(exit_status: int, message: str) -> str:
    """Derive a code from a handler's exit status and captured stderr message."""
    lowered = message.lower()
    if exit_status == exit_code(ErrorCode.NOT_IMPLEMENTED):
        return ErrorCode.NOT_IMPLEMENTED
    if exit_status == exit_code(ErrorCode.CONFIG):
        if "configuration error" in lowered:
            return ErrorCode.CONFIG
        return ErrorCode.USAGE
    if exit_status == 0:
        return ErrorCode.FAILED
    for needle, code in _HINTS:
        if needle in lowered:
            return code
    return ErrorCode.FAILED


def error_line(code: str, message: str, hint: str | None = None) -> str:
    """Serialize the envelope as one JSON line."""
    return json.dumps(envelope(code, message, hint), ensure_ascii=False)


def emit(code: str, message: str, hint: str | None = None) -> None:
    """Write the envelope to stderr as a single line."""
    print(error_line(code, message, hint), file=sys.stderr)


def render_table() -> str:
    """Render the exit-code table from the catalog (the checked-in source of truth)."""
    rows = ["| Code | Exit | Meaning | Hint |", "|---|---|---|---|"]
    for spec in CATALOG:
        rows.append(f"| `{spec.code}` | `{spec.exit_code}` | {spec.summary} | {spec.hint} |")
    return "\n".join(rows)


if __name__ == "__main__":  # pragma: no cover - convenience
    print(render_table())
