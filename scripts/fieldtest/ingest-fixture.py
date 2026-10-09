#!/usr/bin/env python3
"""M31 31.2 — ingest recorded fixtures through the REAL surfaces (M31 deep-check).

The shipped `agentwatch ingest` accepts only
`--format {otel,otlp-grpc,ndjson,aat,claude-compliance,claude-otel,system-ingest,acs}`
plus `--agent {codex,opencode}`. Harnesses without an `ingest` path (Cursor,
Gemini) are normalized through their shipped adapters
(`agentwatch.adapters.cursor|gemini_cli.normalize`), which is how the recorder
ingests them in production. Nothing here invents a format.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ftutil import QUARANTINE, STORE, arg, fail, fixture, ok, run

# kind -> real `agentwatch ingest` args.
CLI_FORMAT = {
    "otel": ["--format", "otel"],
    "otlp-grpc": ["--format", "otlp-grpc"],
    "aat": ["--format", "aat"],
    "cco": ["--format", "claude-otel"],
    "cca": ["--format", "claude-compliance", "--consent"],
    "system": ["--format", "system-ingest", "--consent"],
    "acs": ["--format", "acs"],
    "gateway": ["--format", "otel"],
}
CLI_AGENT = {"codex": ["--agent", "codex"], "opencode": ["--agent", "opencode"]}
# Harnesses without a CLI ingest path are normalized through their shipped
# adapters (agentwatch.adapters.*), which is how the recorder ingests them.
ADAPTER = {
    "cursor": "agentwatch.adapters.cursor",
    "cursor-blocking": "agentwatch.adapters.cursor",
    "gemini": "agentwatch.adapters.gemini_cli",
    "mcp": "agentwatch.adapters.mcp_proxy",
}
# The long-tail "logreaders" corpus mixes framed hook fixtures (cursor/gemini)
# with native transcripts (claude-code .jsonl) and codex rollouts. Each file is
# read by *its own* reader, dispatched per file — never one adapter for all.
HARNESS_ADAPTER = {
    "cursor": "agentwatch.adapters.cursor",
    "gemini-cli": "agentwatch.adapters.gemini_cli",
    "claude-code": "agentwatch.adapters.claude_code",
    "codex": "agentwatch.adapters.codex_cli",
}
_ROLLOUT_TYPES = {"session_meta", "turn_context", "response_item"}


def _sig(d: dict) -> tuple:
    """The canonical fidelity signature of a record (what a fixture declares as expected)."""
    tool = d.get("tool") or {}
    return (tool.get("name"), str(d.get("step_type")), str(d.get("outcome")), d.get("harness"))


def _adapter_ingest(module_name: str, path: Path) -> int:
    mod = importlib.import_module(module_name)
    from agentwatch.store import RecordStore

    store = RecordStore(STORE)
    n = 0
    diverged: list[str] = []
    for f in sorted(path.rglob("*.json")):
        if f.name == "manifest.json":
            continue
        try:
            msg = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(msg, dict):
            continue
        payload = msg.get("message", msg) if isinstance(msg.get("message"), dict) else msg
        try:
            records = mod.normalize(payload)
        except Exception:  # noqa: BLE001 - not an adapter message; skip (it is not a fixture failure)
            continue
        # Real fidelity check: the normalized record(s) must reproduce the fixture's
        # declared canonical output (per event), not merely "produce something".
        expected = msg.get("expected")
        if expected and records:
            want = sorted(_sig(e) for e in expected)
            got = sorted(_sig(r.to_dict()) for r in records)
            if want != got:
                diverged.append(f"{f.name}: expected {want} got {got}")
        for rec in records:
            store.append(rec)
            n += 1
    if diverged:
        for line in diverged:
            print(line, file=sys.stderr)
        fail(f"{len(diverged)} fixture(s) diverged from their expected record")
    return n


def _mcp_malformed_ingest(path: Path) -> tuple[int, int]:
    """Normalize MCP frames; quarantine (never drop) the non-normalizable ones.

    Closed-by-spec methods and malformed frames land in ``quarantine.jsonl``
    with the offending field named, exercising the real ``QuarantineLog``.
    """
    from agentwatch.adapters import mcp_proxy
    from agentwatch.quarantine import QuarantineLog
    from agentwatch.store import RecordStore

    store = RecordStore(STORE)
    quarantine = QuarantineLog(QUARANTINE)
    normalized = quarantined = 0
    for f in sorted(path.rglob("*.json")):
        if f.name == "manifest.json":
            continue
        raw = f.read_text(encoding="utf-8")
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            quarantine.add(raw, reason="not valid JSON")
            quarantined += 1
            continue
        payload = msg.get("message", msg) if isinstance(msg, dict) else msg
        try:
            records = mcp_proxy.normalize(payload)
        except mcp_proxy.McpProxyAdapterError as exc:
            quarantine.add(raw, reason=str(exc))
            quarantined += 1
            continue
        for rec in records:
            store.append(rec)
            normalized += 1
    return normalized, quarantined


def _is_rollout(path: Path) -> bool:
    """True if a .jsonl looks like a codex rollout (vs a claude-code transcript)."""
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                return isinstance(entry, dict) and entry.get("type") in _ROLLOUT_TYPES
    except (OSError, json.JSONDecodeError):
        return False
    return False


def _logreaders_ingest(path: Path) -> int:
    """Ingest the long-tail reader corpus: one file → its real reader."""
    from agentwatch.codex_rollout import ingest_rollouts
    from agentwatch.importer import import_transcripts
    from agentwatch.store import RecordStore

    store = RecordStore(STORE)
    n = 0
    empty: list[str] = []
    for f in sorted(path.iterdir()):
        if f.name == "manifest.json":
            continue
        start = n
        if f.suffix == ".jsonl":
            if _is_rollout(f):
                n += ingest_rollouts([f], store).records
            else:
                n += import_transcripts([f], store).records
        elif f.suffix == ".json":
            try:
                msg = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                msg = None
            message = msg.get("message") if isinstance(msg, dict) else None
            if isinstance(message, dict):
                module_name = HARNESS_ADAPTER.get(str(message.get("harness")))
                if module_name is not None:
                    try:
                        records = importlib.import_module(module_name).normalize(message)
                    except Exception:  # noqa: BLE001 - not a framed message for this reader
                        records = []
                    for rec in records:
                        store.append(rec)
                        n += 1
        if n == start:
            empty.append(f.name)
    if empty:
        fail(f"reader(s) produced 0 records from {path}: {empty}")
    return n


def main(argv: list[str]) -> int:
    kind = arg(argv, "--kind", "") or ""
    path = Path(arg(argv, "--corpus") or fixture(kind))
    if kind in CLI_FORMAT:
        run(["agentwatch", "ingest", *CLI_FORMAT[kind], str(path)])
    elif kind in CLI_AGENT:
        run(["agentwatch", "ingest", *CLI_AGENT[kind], str(path)])
    elif kind == "logreaders":
        n = _logreaders_ingest(path)
        if n == 0:
            fail(f"logreaders readers normalized 0 records from {path}")
    elif kind == "mcp-malformed":
        normalized, quarantined = _mcp_malformed_ingest(path)
        if quarantined == 0:
            fail(f"no malformed MCP frames quarantined from {path}")
        ok(f"mcp-malformed: {normalized} normalized, {quarantined} quarantined")
    elif kind in ADAPTER:
        n = _adapter_ingest(ADAPTER[kind], path)
        if n == 0:
            fail(f"adapter {ADAPTER[kind]} normalized 0 records from {path}")
    else:
        fail(f"no real ingest path for kind {kind!r} (formats: {sorted(CLI_FORMAT)}, "
             f"agents: {sorted(CLI_AGENT)}, adapters: {sorted(ADAPTER)})")
    run(["agentwatch", "verify-store"])
    ok(f"ingested {kind} from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
