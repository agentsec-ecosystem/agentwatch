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
    "logreaders": "agentwatch.adapters.claude_code",
}


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


def main(argv: list[str]) -> int:
    kind = arg(argv, "--kind", "") or ""
    path = Path(arg(argv, "--corpus") or fixture(kind))
    if kind in CLI_FORMAT:
        run(["agentwatch", "ingest", *CLI_FORMAT[kind], str(path)])
    elif kind in CLI_AGENT:
        run(["agentwatch", "ingest", *CLI_AGENT[kind], str(path)])
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
