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
from _ftutil import STORE, arg, fail, fixture, ok, run

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
    "mcp-malformed": "agentwatch.adapters.mcp_proxy",
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


def _adapter_ingest(module_name: str, path: Path) -> int:
    mod = importlib.import_module(module_name)
    from agentwatch.store import RecordStore

    store = RecordStore(STORE)
    n = 0
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
        for rec in records:
            store.append(rec)
            n += 1
    return n


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
    for f in sorted(path.iterdir()):
        if f.name == "manifest.json":
            continue
        if f.suffix == ".jsonl":
            if _is_rollout(f):
                n += ingest_rollouts([f], store).records
            else:
                n += import_transcripts([f], store).records
            continue
        if f.suffix != ".json":
            continue
        try:
            msg = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        message = msg.get("message") if isinstance(msg, dict) else None
        if not isinstance(message, dict):
            continue
        module_name = HARNESS_ADAPTER.get(str(message.get("harness")))
        if module_name is None:
            continue
        try:
            records = importlib.import_module(module_name).normalize(message)
        except Exception:  # noqa: BLE001 - not a framed message for this reader
            continue
        for rec in records:
            store.append(rec)
            n += 1
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
