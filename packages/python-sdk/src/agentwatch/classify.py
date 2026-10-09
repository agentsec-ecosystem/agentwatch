"""Deterministic argument classifier (M17 S3, PRD 33).

A small, **published and versioned** pattern table that turns a record's tool
arguments into descriptive facts: files touched, side-effecting commands, network
destinations, VCS actions, and credential-adjacent touches. Every fact carries a
``confidence`` of ``exact`` (a structured argument, e.g. ``Write.file_path``) or
``heuristic`` (a token inside a shell command). Anything not matched lands in the
surfaced ``unclassified`` bucket — shell parsing is a bottomless pit, so the
classifier never claims completeness.

Facts only: there is no score, severity, or verdict. "Exfiltration" is a human's
or agentpolicy's judgement, not this module's (PRD 14).

Shared by S3 (:mod:`agentwatch.impact`), S18 (:mod:`agentwatch.blame`), and S25
(:mod:`agentwatch.denials`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CLASSIFIER_VERSION = "cls1"

EXACT = "exact"
HEURISTIC = "heuristic"

FILE_WRITE = "file:write"
FILE_EDIT = "file:edit"
FILE_DELETE = "file:delete"
FILE_READ = "file:read"
CMD_INSTALL = "command:install"
CMD_MIGRATION = "command:migration"
CMD_SERVICE = "command:service-restart"
CMD_DESTRUCTIVE = "command:destructive"
NETWORK = "network:destination"
VCS = "vcs:action"
CREDENTIAL = "credential:adjacent"
UNCLASSIFIED = "unclassified"

CATEGORIES: tuple[str, ...] = (
    FILE_WRITE,
    FILE_EDIT,
    FILE_DELETE,
    FILE_READ,
    CMD_INSTALL,
    CMD_MIGRATION,
    CMD_SERVICE,
    CMD_DESTRUCTIVE,
    NETWORK,
    VCS,
    CREDENTIAL,
    UNCLASSIFIED,
)

# Priority order for the impact "widest action" line (most consequential first).
WIDEST_ORDER: tuple[str, ...] = (
    CMD_DESTRUCTIVE,
    FILE_DELETE,
    CMD_SERVICE,
    CMD_MIGRATION,
    CMD_INSTALL,
    FILE_WRITE,
    FILE_EDIT,
    CREDENTIAL,
    NETWORK,
    VCS,
    FILE_READ,
    UNCLASSIFIED,
)


@dataclass(frozen=True)
class PatternRule:
    """One published classifier rule (category + confidence + regex + docs)."""

    id: str
    category: str
    confidence: str
    regex: re.Pattern[str]
    detail: str


def _rule(rule_id: str, category: str, confidence: str, pattern: str, detail: str) -> PatternRule:
    return PatternRule(rule_id, category, confidence, re.compile(pattern, re.IGNORECASE), detail)


# The versioned table. `cls1` — see docs/design/impact-classification.md.
PATTERNS: tuple[PatternRule, ...] = (
    # -- side-effecting commands (heuristic: a token inside a shell string) --
    _rule(
        "install/pip",
        CMD_INSTALL,
        HEURISTIC,
        r"\b(?:pip|pip3|uv\s+pip)\s+install\b",
        "python package install",
    ),
    _rule(
        "install/npm",
        CMD_INSTALL,
        HEURISTIC,
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:i|install|add)\b",
        "node package install",
    ),
    _rule(
        "install/brew",
        CMD_INSTALL,
        HEURISTIC,
        r"\b(?:brew|port|nix-env)\s+(?:install|add)\b",
        "system package install",
    ),
    _rule(
        "install/apt",
        CMD_INSTALL,
        HEURISTIC,
        r"\b(?:apt|apt-get|dnf|yum|apk|pacman)\s+"
        r"(?:install|add|-S)\b",
        "system package install",
    ),
    _rule(
        "install/cargo",
        CMD_INSTALL,
        HEURISTIC,
        r"\b(?:cargo|go|gem|poetry|conda)\s+"
        r"(?:add|install|get)\b",
        "language package install",
    ),
    _rule(
        "migrate/alembic",
        CMD_MIGRATION,
        HEURISTIC,
        r"\balembic\s+(?:upgrade|downgrade)\b",
        "database migration",
    ),
    _rule(
        "migrate/django",
        CMD_MIGRATION,
        HEURISTIC,
        r"\bmanage\.py\s+migrate\b|"
        r"\bdjango-admin\s+migrate\b",
        "database migration",
    ),
    _rule(
        "migrate/rails",
        CMD_MIGRATION,
        HEURISTIC,
        r"\brails\s+db:migrate\b|"
        r"\bprisma\s+migrate\b|\bflyway\b|\bsqitch\b",
        "database migration",
    ),
    _rule(
        "service/systemctl",
        CMD_SERVICE,
        HEURISTIC,
        r"\bsystemctl\s+(?:restart|start|stop|reload)\b",
        "service control",
    ),
    _rule(
        "service/service",
        CMD_SERVICE,
        HEURISTIC,
        r"\bservice\s+\S+\s+(?:restart|start|stop)\b|"
        r"\blaunchctl\b|\bpm2\s+(?:restart|reload)\b|\bsupervisorctl\b",
        "service control",
    ),
    _rule(
        "service/docker",
        CMD_SERVICE,
        HEURISTIC,
        r"\bdocker(?:\s+compose)?\s+"
        r"(?:restart|up|down|stop|start|kill)\b",
        "container/service control",
    ),
    _rule(
        "service/kubectl",
        CMD_SERVICE,
        HEURISTIC,
        r"\bkubectl\s+(?:rollout|restart|delete|apply)\b|"
        r"\bhelm\s+(?:upgrade|install|uninstall)\b",
        "cluster workload control",
    ),
    _rule(
        "destructive/rm",
        CMD_DESTRUCTIVE,
        HEURISTIC,
        r"\brm\s+-[a-z]*[rf][a-z]*\b",
        "recursive/forced delete",
    ),
    _rule(
        "destructive/sql",
        CMD_DESTRUCTIVE,
        HEURISTIC,
        r"\bdrop\s+(?:database|table|schema)\b|"
        r"\btruncate\s+table\b|\bdelete\s+from\b",
        "destructive SQL",
    ),
    _rule(
        "destructive/disk",
        CMD_DESTRUCTIVE,
        HEURISTIC,
        r"\bmkfs(?:\.\w+)?\b|\bshred\b|"
        r"\bdd\s+if=/dev/(?:zero|urandom)\b",
        "disk-destructive command",
    ),
    _rule(
        "destructive/git",
        CMD_DESTRUCTIVE,
        HEURISTIC,
        r"\bgit\s+reset\s+--hard\b|"
        r"\bgit\s+clean\s+-[a-z]*f\b|\bgit\s+push\s+--force\b|\bgit\s+branch\s+-D\b",
        "history/worktree-destructive git",
    ),
    _rule(
        "destructive/process",
        CMD_DESTRUCTIVE,
        HEURISTIC,
        r"\bkill\s+-9\b|\bpkill\b|"
        r"\bchmod\s+-R\b|\bchown\s+-R\b",
        "process/permission-destructive",
    ),
    # -- file mutation inside a shell command (heuristic) --
    _rule(
        "file/redirect", FILE_WRITE, HEURISTIC, r">>?\s*(?P<target>[^\s;&|>]+)", "shell redirection"
    ),
    _rule(
        "file/tee",
        FILE_WRITE,
        HEURISTIC,
        r"\btee\b(?:\s+-\S+)*\s+(?P<target>[^\s;&|]+)",
        "tee write",
    ),
    _rule(
        "file/sed",
        FILE_EDIT,
        HEURISTIC,
        r"\bsed\s+-i\S*(?:\s+-e\s+\S+)?\s+"
        r"(?P<target>[^\s;&|]+)",
        "in-place edit",
    ),
    _rule(
        "file/cp",
        FILE_WRITE,
        HEURISTIC,
        r"\bcp\b(?:\s+-\S+)*\s+\S+\s+(?P<target>[^\s;&|]+)",
        "copy",
    ),
    _rule(
        "file/mv",
        FILE_WRITE,
        HEURISTIC,
        r"\bmv\b(?:\s+-\S+)*\s+\S+\s+(?P<target>[^\s;&|]+)",
        "move",
    ),
    _rule(
        "file/touch",
        FILE_WRITE,
        HEURISTIC,
        r"\btouch\b(?:\s+-\S+)*\s+(?P<target>[^\s;&|]+)",
        "create file",
    ),
    _rule(
        "file/rm",
        FILE_DELETE,
        HEURISTIC,
        r"\brm\b(?:\s+-\S+)*\s+(?P<target>[^\s;&|]+)",
        "shell delete",
    ),
    _rule(
        "file/rmdir",
        FILE_DELETE,
        HEURISTIC,
        r"\brmdir\b(?:\s+-\S+)*\s+(?P<target>[^\s;&|]+)",
        "shell delete directory",
    ),
    # -- network --
    _rule(
        "net/curl",
        NETWORK,
        HEURISTIC,
        r"\b(?:curl|wget)\b.*?(?P<target>"
        r"(?:https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s'\";|]*)?)",
        "outbound fetch",
    ),
    _rule(
        "net/scp",
        NETWORK,
        HEURISTIC,
        r"\b(?:ssh|scp|rsync|nc|telnet)\b(?:\s+-\S+)*\s+"
        r"(?P<target>[^\s;&|@]+@?[^\s;&|]*)",
        "remote transfer/session",
    ),
    # -- vcs --
    _rule("vcs/git", VCS, HEURISTIC, r"\bgit\s+(?P<target>[a-z-]+)", "git action"),
    _rule("vcs/gh", VCS, HEURISTIC, r"\bgh\s+(?P<target>[a-z-]+)", "github CLI action"),
    # -- credential-adjacent --
    _rule(
        "cred/env",
        CREDENTIAL,
        HEURISTIC,
        r"(?:^|[\s'\"/])(?P<target>\.env(?:\.[A-Za-z0-9]+)?)\b",
        "dotenv file",
    ),
    _rule(
        "cred/aws",
        CREDENTIAL,
        HEURISTIC,
        r"(?P<target>~/\.aws/[^\s'\";|]+|\.aws/credentials)",
        "AWS credentials",
    ),
    _rule(
        "cred/ssh",
        CREDENTIAL,
        HEURISTIC,
        r"(?P<target>~/\.ssh/[^\s'\";|]+|id_(?:rsa|ed25519))",
        "SSH key material",
    ),
    _rule(
        "cred/misc",
        CREDENTIAL,
        HEURISTIC,
        r"(?P<target>\.netrc|\.pypirc|\.npmrc|\.docker/config\.json|"
        r"\.kube/config|keychain|security\s+find-generic-password)",
        "credential store",
    ),
)

# Structured tools whose path argument is exact.
_WRITE_TOOLS = frozenset({"write", "notebookedit", "create", "str_replace_editor"})
_EDIT_TOOLS = frozenset({"edit", "multiedit", "str_replace", "apply_patch"})
_DELETE_TOOLS = frozenset({"delete", "remove"})
_READ_TOOLS = frozenset({"read", "glob", "grep", "ls", "view"})
_SHELL_TOOLS = frozenset({"bash", "shell", "run", "execute", "terminal", "computer"})

_PATH_KEYS = ("file_path", "path", "notebook_path", "filename", "file")


@dataclass(frozen=True)
class Fact:
    """One descriptive classification of a record (never a verdict)."""

    category: str
    confidence: str
    detail: str
    target: str | None = None


def _arguments_path(arguments: Mapping[str, Any]) -> str | None:
    for key in _PATH_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _shell_command(arguments: Mapping[str, Any]) -> str | None:
    for key in ("command", "cmd", "script", "input"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _target_for(category: str, match: re.Match[str], command: str) -> str | None:
    group = match.groupdict().get("target")
    if group:
        return group.strip()
    if match.groups():
        return match.group(1)
    words = command.strip().split()
    return words[0] if words else None


def classify_command(command: str) -> list[Fact]:
    """Classify a shell command string into facts (heuristic, deterministic)."""
    facts: list[Fact] = []
    seen: set[tuple[str, str | None]] = set()
    for rule in PATTERNS:
        match = rule.regex.search(command)
        if match is None:
            continue
        target = _target_for(rule.category, match, command)
        key = (rule.category, target)
        if key in seen:
            continue
        seen.add(key)
        facts.append(Fact(rule.category, rule.confidence, rule.detail, target))
    if not facts:
        facts.append(Fact(UNCLASSIFIED, HEURISTIC, "unrecognized command", None))
    return facts


def classify_arguments(
    arguments: Mapping[str, Any] | None,
    *,
    tool_name: str,
    server: str | None = None,
) -> list[Fact]:
    """Classify one tool call's arguments into facts."""
    if server is not None:
        return [Fact(NETWORK, HEURISTIC, f"MCP server {server}", server)]
    name = tool_name.lower()
    args: Mapping[str, Any] = arguments or {}
    if name in _WRITE_TOOLS:
        return [Fact(FILE_WRITE, EXACT, "structured write", _arguments_path(args))]
    if name in _EDIT_TOOLS:
        return [Fact(FILE_EDIT, EXACT, "structured edit", _arguments_path(args))]
    if name in _DELETE_TOOLS:
        return [Fact(FILE_DELETE, EXACT, "structured delete", _arguments_path(args))]
    if name in _SHELL_TOOLS:
        command = _shell_command(args)
        if command is None:
            return [Fact(UNCLASSIFIED, HEURISTIC, "shell with no captured command", None)]
        return classify_command(command)
    if name in _READ_TOOLS:
        return [Fact(FILE_READ, HEURISTIC, "read-only tool", _arguments_path(args))]
    if name in {"webfetch", "websearch"}:
        return [Fact(NETWORK, HEURISTIC, "web fetch/search", _url_host(args))]
    return [Fact(UNCLASSIFIED, EXACT, f"unclassified tool {tool_name}", None)]


def _url_host(arguments: Mapping[str, Any]) -> str | None:
    for key in ("url", "query"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            match = re.search(r"(?:https?://)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})", value)
            if match is not None:
                return match.group(1)
    return None


def _classify_system(record: Any) -> list[Fact]:
    """Facts for the foreign system-effects layer (M29 SYS-1).

    Network destinations are structural truth carried on ``tool.server`` even in
    metadata-only mode; a process exec is classified from its captured command.
    The ``system:`` tool namespace is machine-distinguishable from hook tools.
    """
    name = record.tool.name
    arguments = record.tool.arguments or {}
    if name == "system:network-connect":
        target = record.tool.server or arguments.get("target")
        detail = target if isinstance(target, str) else None
        return [Fact(NETWORK, EXACT, "syscall network connect", detail)]
    if name == "system:process-exec":
        exe = arguments.get("exe")
        if isinstance(exe, str) and exe:
            return classify_command(exe)
    return [Fact(UNCLASSIFIED, EXACT, f"unclassified system event {name}", None)]


def classify_record(record: Any) -> list[Fact]:
    """Classify a stored record; metadata-only records say so explicitly."""
    if record.tool.name.startswith("system:"):
        return _classify_system(record)
    arguments = record.tool.arguments
    if arguments is None:
        return [Fact(UNCLASSIFIED, EXACT, "arguments not captured (metadata-only)", None)]
    return classify_arguments(arguments, tool_name=record.tool.name, server=record.tool.server)


def pattern_table() -> tuple[dict[str, str], ...]:
    """A machine-readable view of the published table (for docs and tests)."""
    return tuple(
        {
            "id": rule.id,
            "category": rule.category,
            "confidence": rule.confidence,
            "pattern": rule.regex.pattern,
            "detail": rule.detail,
        }
        for rule in PATTERNS
    )


# ---------------------------------------------------------------------------
# cls2 — test/build/lint outcome classes (M30 EXT-4, PRD 33)
#
# `cls2` is a **separate, versioned** table: it does not touch the `cls1`
# pattern table above, so `cls1` outputs stay reproducible. A `cls2` fact names
# the command *kind* (`outcome:test` / `outcome:build` / `outcome:lint`) and its
# exit-status class (`pass` / `fail` / `unknown`) from the tool outcome or an
# explicit exit code. `pass`/`fail` is a fact about an exit, never a verdict.
# ---------------------------------------------------------------------------

OUTCOME_VERSION = "cls2"

OUTCOME_TEST = "outcome:test"
OUTCOME_BUILD = "outcome:build"
OUTCOME_LINT = "outcome:lint"

OUTCOME_CATEGORIES: tuple[str, ...] = (OUTCOME_TEST, OUTCOME_BUILD, OUTCOME_LINT)

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class OutcomeRule:
    """One published cls2 outcome rule (kind + regex + docs)."""

    id: str
    category: str
    regex: re.Pattern[str]
    detail: str


def _outcome_rule(rule_id: str, category: str, pattern: str, detail: str) -> OutcomeRule:
    return OutcomeRule(rule_id, category, re.compile(pattern, re.IGNORECASE), detail)


# Order matters: specific test/lint targets precede the generic build rules so
# `make test`, `make lint`, and `npm run build` classify deterministically. The
# first matching rule wins.
OUTCOME_PATTERNS: tuple[OutcomeRule, ...] = (
    # -- tests --
    _outcome_rule(
        "test/pytest",
        OUTCOME_TEST,
        r"\b(?:python[0-9.]*\s+-m\s+)?pytest\b",
        "python test runner",
    ),
    _outcome_rule(
        "test/unittest",
        OUTCOME_TEST,
        r"\b(?:python[0-9.]*\s+-m\s+)?unittest\b",
        "python unittest",
    ),
    _outcome_rule("test/tox", OUTCOME_TEST, r"\b(?:tox|nox)\b", "python test matrix"),
    _outcome_rule("test/js", OUTCOME_TEST, r"\b(?:jest|vitest|mocha|ava)\b", "js test runner"),
    _outcome_rule(
        "test/node",
        OUTCOME_TEST,
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b",
        "node test script",
    ),
    _outcome_rule("test/go", OUTCOME_TEST, r"\bgo\s+test\b", "go test"),
    _outcome_rule("test/cargo", OUTCOME_TEST, r"\bcargo\s+test\b", "cargo test"),
    _outcome_rule("test/dotnet", OUTCOME_TEST, r"\bdotnet\s+test\b", "dotnet test"),
    _outcome_rule(
        "test/jvm",
        OUTCOME_TEST,
        r"\b(?:mvn|gradle)\s+(?:test|verify)\b",
        "jvm test",
    ),
    _outcome_rule(
        "test/other",
        OUTCOME_TEST,
        r"\b(?:rspec|phpunit|pester|bats)\b",
        "test runner",
    ),
    _outcome_rule("test/make", OUTCOME_TEST, r"\bmake\s+(?:test|check)\b", "make test target"),
    # -- lint / type-check / format-check --
    _outcome_rule(
        "lint/python",
        OUTCOME_LINT,
        r"\b(?:ruff|flake8|pylint|pyright|mypy|pydocstyle)\b",
        "python lint/type-check",
    ),
    _outcome_rule(
        "lint/js",
        OUTCOME_LINT,
        r"\b(?:eslint|prettier|stylelint|biome)\b",
        "js/ts lint/format-check",
    ),
    _outcome_rule(
        "lint/rust",
        OUTCOME_LINT,
        r"\bcargo\s+(?:clippy|fmt)\b",
        "rust lint/format-check",
    ),
    _outcome_rule("lint/go", OUTCOME_LINT, r"\bgolangci-lint\b|\bgo\s+vet\b", "go lint/vet"),
    _outcome_rule(
        "lint/ruby", OUTCOME_LINT, r"\b(?:rubocop|standardrb)\b", "ruby lint"
    ),
    _outcome_rule("lint/shell", OUTCOME_LINT, r"\bshellcheck\b|\bshfmt\b", "shell lint"),
    _outcome_rule("lint/make", OUTCOME_LINT, r"\bmake\s+(?:lint|check)\b", "make lint target"),
    # -- builds / compiles --
    _outcome_rule(
        "build/node",
        OUTCOME_BUILD,
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?build\b",
        "node build script",
    ),
    _outcome_rule("build/tsc", OUTCOME_BUILD, r"\btsc\b|\btsc\s+--noEmit\b", "typescript compiler"),
    _outcome_rule(
        "build/bundler",
        OUTCOME_BUILD,
        r"\b(?:webpack|vite|rollup|esbuild|parcel)\b",
        "js bundler",
    ),
    _outcome_rule("build/cargo", OUTCOME_BUILD, r"\bcargo\s+build\b", "cargo build"),
    _outcome_rule("build/go", OUTCOME_BUILD, r"\bgo\s+build\b", "go build"),
    _outcome_rule(
        "build/dotnet", OUTCOME_BUILD, r"\bdotnet\s+(?:build|publish)\b", "dotnet build"
    ),
    _outcome_rule(
        "build/jvm",
        OUTCOME_BUILD,
        r"\b(?:mvn|gradle)\s+(?:package|compile|assemble|build)\b",
        "jvm build",
    ),
    _outcome_rule(
        "build/native",
        OUTCOME_BUILD,
        r"\bcmake\s+--build\b|\bninja\b|\bbazel\s+build\b",
        "native build",
    ),
    _outcome_rule(
        "build/docker",
        OUTCOME_BUILD,
        r"\bdocker(?:\s+compose)?\s+build\b",
        "container build",
    ),
    _outcome_rule("build/make", OUTCOME_BUILD, r"\bmake\b|\bcmake\b", "make/build"),
)

_EXIT_CODE_KEYS = ("exit_code", "exit_status", "returncode", "code")


@dataclass(frozen=True)
class OutcomeFact:
    """A cls2 derived fact about a test/build/lint command (never a verdict)."""

    category: str
    status: str
    rule_id: str
    confidence: str


def _status_from(*, exit_code: int | None, succeeded: bool | None) -> str:
    if exit_code is not None:
        return PASS if exit_code == 0 else FAIL
    if succeeded is not None:
        return PASS if succeeded else FAIL
    return UNKNOWN


def classify_outcome(
    command: str,
    *,
    exit_code: int | None = None,
    succeeded: bool | None = None,
) -> OutcomeFact | None:
    """Classify a shell command as a cls2 outcome, or ``None`` when it is not one."""
    for rule in OUTCOME_PATTERNS:
        if rule.regex.search(command):
            return OutcomeFact(
                category=rule.category,
                status=_status_from(exit_code=exit_code, succeeded=succeeded),
                rule_id=rule.id,
                confidence=HEURISTIC,
            )
    return None


def _record_exit_code(record: Any) -> int | None:
    response = record.tool.response
    if not isinstance(response, Mapping):
        return None
    for key in _EXIT_CODE_KEYS:
        value = response.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def classify_record_outcome(record: Any) -> OutcomeFact | None:
    """A cls2 outcome fact for a shell record, or ``None`` when not an outcome command."""
    if record.tool.name.lower() not in _SHELL_TOOLS:
        return None
    command = _shell_command(record.tool.arguments or {})
    if command is None:
        return None
    outcome = record.outcome.value
    succeeded = True if outcome == "ok" else False if outcome in {"error", "denied"} else None
    return classify_outcome(
        command,
        exit_code=_record_exit_code(record),
        succeeded=succeeded,
    )


def outcome_table() -> tuple[dict[str, str], ...]:
    """A machine-readable view of the published cls2 table (for docs and tests)."""
    return tuple(
        {
            "id": rule.id,
            "category": rule.category,
            "confidence": HEURISTIC,
            "pattern": rule.regex.pattern,
            "detail": rule.detail,
        }
        for rule in OUTCOME_PATTERNS
    )


__all__ = [
    "CATEGORIES",
    "CLASSIFIER_VERSION",
    "CMD_DESTRUCTIVE",
    "CMD_INSTALL",
    "CMD_MIGRATION",
    "CMD_SERVICE",
    "CREDENTIAL",
    "EXACT",
    "FILE_DELETE",
    "FILE_EDIT",
    "FILE_READ",
    "FILE_WRITE",
    "Fact",
    "FAIL",
    "HEURISTIC",
    "NETWORK",
    "OUTCOME_BUILD",
    "OUTCOME_CATEGORIES",
    "OUTCOME_LINT",
    "OUTCOME_PATTERNS",
    "OUTCOME_TEST",
    "OUTCOME_VERSION",
    "OutcomeFact",
    "OutcomeRule",
    "PASS",
    "PATTERNS",
    "UNCLASSIFIED",
    "UNKNOWN",
    "VCS",
    "WIDEST_ORDER",
    "classify_arguments",
    "classify_command",
    "classify_outcome",
    "classify_record",
    "classify_record_outcome",
    "outcome_table",
    "pattern_table",
]
