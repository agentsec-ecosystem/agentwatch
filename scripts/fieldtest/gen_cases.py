#!/usr/bin/env python3
"""Generate field-test case specs + step scripts from one registry (M23).

Run::

    python3 scripts/fieldtest/gen_cases.py

Every case runs and is pass/fail. There is no skip: a case that does not pass
fails. Step scripts source ``lib.sh``, run assertions with ``ft_assert`` /
``ft_assert_recorder``, and finish with ``ft_finalize`` (which sets
``FT_CASE_STATUS`` to pass only when every assertion held).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
STEPS_DIR = CASES_DIR / "steps"
CUSTOM_SPECS = {"FT-15-detector-validation.md"}

CASES: list[dict[str, str]] = [
    {"id": "FT-01", "title": "Fresh install → first record", "kind": "recorder_smoke", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-4,R2"},
    {"id": "FT-01b", "title": "First-run timing ≤ 15 min", "kind": "first_run_timing", "layer": "recorder", "llm": "no", "requires": "python", "prd": "13 NFR-4,R2"},
    {"id": "FT-02", "title": "Replay matches transcript", "kind": "recorder_replay", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "R8"},
    {"id": "FT-03", "title": "OTLP export → Jaeger", "kind": "otel_export", "layer": "recorder", "llm": "no", "requires": "docker,jaeger", "prd": "R4"},
    {"id": "FT-04", "title": "Redaction attack, 0 leaks", "kind": "redaction", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "R7,06"},
    {"id": "FT-05", "title": "Store tamper → fail closed", "kind": "tamper", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F4"},
    {"id": "FT-06", "title": "Long session / soak", "kind": "soak", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-1", "count": "1000"},
    {"id": "FT-06b", "title": "In-repo corpus soak + validate", "kind": "bulk_corpus", "layer": "analyst", "llm": "no", "requires": "docker", "prd": "13 NFR-1,30"},
    {"id": "FT-07", "title": "agentwatch demo proof", "kind": "demo", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "S31"},
    {"id": "FT-08", "title": "Checkpoint notarize + sign", "kind": "checkpoint", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "W7/W9"},
    {"id": "FT-09", "title": "Product E2E (Playwright)", "kind": "analyst", "layer": "analyst", "llm": "no", "requires": "docker,node", "prd": "A5"},
    {"id": "FT-10", "title": "Offline / no egress", "kind": "offline", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "R6,NFR-9"},
    {"id": "FT-11", "title": "LLM agent loop (OMLX)", "kind": "llm", "layer": "recorder", "llm": "yes", "requires": "docker,omlx", "prd": "S11,30"},
    {"id": "FT-11b", "title": "3-way LLM detector validation (OMLX)", "kind": "llm_validation", "layer": "analyst", "llm": "yes", "requires": "docker,omlx", "prd": "29,30"},
    {"id": "FT-11c", "title": "Cross-framework agent traces", "kind": "cross_framework", "layer": "recorder", "llm": "no", "requires": "docker,jaeger", "prd": "27,12 R10"},
    {"id": "FT-11d", "title": "1M synthetic corpus LLM pilot (M13.1)", "kind": "synthetic_llm", "layer": "analyst", "llm": "yes", "requires": "docker,omlx", "prd": "29,30"},
    {"id": "FT-12", "title": "Bad config → fail closed", "kind": "config_bad", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F7,06 #1"},
    {"id": "FT-13", "title": "Store tamper + repair", "kind": "tamper_repair", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F4"},
    {"id": "FT-14", "title": "Daemon SIGKILL → recording-gap", "kind": "gap", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F1,21 B3"},
    {"id": "FT-15", "title": "Detector validation (ported matrix)", "kind": "detector", "layer": "analyst", "llm": "no", "requires": "docker,node", "prd": "30,12 A2", "spec": "custom"},
    {"id": "FT-15b", "title": "Detector corpus compatibility diagnostic", "kind": "detector_corpus", "layer": "analyst", "llm": "no", "requires": "docker", "prd": "30,12 A2"},
    {"id": "FT-15c", "title": "Full 100k-trace corpus validation", "kind": "full_corpus", "layer": "analyst", "llm": "no", "requires": "docker", "prd": "30,12 A2"},
    {"id": "FT-16", "title": "Spool + exactly-once", "kind": "spool", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F2,21 B1"},
    {"id": "FT-17", "title": "Quarantine + reprocess", "kind": "quarantine", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F8,21 B4"},
    {"id": "FT-18", "title": "Store full → stop + surface", "kind": "store_full", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F3"},
    {"id": "FT-19", "title": "Export endpoint down → resume", "kind": "otel_export_down", "layer": "recorder", "llm": "no", "requires": "docker,jaeger", "prd": "17 F5"},
    {"id": "FT-20", "title": "Self-test fail → export blocked", "kind": "selftest_gate", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F6"},
    {"id": "FT-20b", "title": "Self-test visible in health", "kind": "health_selftest", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-9"},
    {"id": "FT-22", "title": "Clock skew → degraded", "kind": "clock_skew", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F9"},
    {"id": "FT-23", "title": "Partial session incomplete", "kind": "partial_session", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "17 F10"},
    {"id": "FT-24", "title": "/healthz states never lie", "kind": "health", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-12"},
    {"id": "FT-25", "title": "Hook latency + async ordering", "kind": "soak", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "28 P1", "count": "500"},
    {"id": "FT-26", "title": "Bounded store/logs + posture", "kind": "posture", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "28 F5/F6"},
    {"id": "FT-27", "title": "Portability: host-native run", "kind": "portability", "layer": "recorder", "llm": "no", "requires": "python", "prd": "13 NFR-6"},
    {"id": "FT-28", "title": "Scale 10k/day", "kind": "soak", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-7", "count": "10000", "min": "0.99", "interval": "0.01"},
    {"id": "FT-29", "title": "Multi-harness adapters conformance", "kind": "conformance", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "27,12 R10"},
    {"id": "FT-30", "title": "Store-format migration", "kind": "migrate", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "21"},
    {"id": "FT-31", "title": "Least-privilege on shared box", "kind": "posture", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "28 F5"},
    {"id": "FT-32", "title": "UI a11y", "kind": "a11y", "layer": "analyst", "llm": "no", "requires": "docker,node", "prd": "13 NFR-10"},
    {"id": "FT-33", "title": "Self-observability contract", "kind": "metrics", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "13 NFR-12"},
    {"id": "FT-34", "title": "Usage/cost accounting", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "20,S6", "cmd": "cost --by tool"},
    {"id": "FT-35", "title": "Capture-fidelity matrix", "kind": "fidelity", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "25"},
    {"id": "FT-36", "title": "Playwright E2E screenshots", "kind": "playwright_shots", "layer": "analyst", "llm": "no", "requires": "docker,node", "prd": "A5,NFR-10"},
    {"id": "CUJ-08", "title": "Incident → evidence (flagship)", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-8", "cmd": "search --tool Bash --outcome error"},
    {"id": "CUJ-09", "title": "Recorder trust report", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-9", "cmd": "coverage"},
    {"id": "CUJ-10", "title": "Cost answer", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-10", "cmd": "cost --by project"},
    {"id": "CUJ-11", "title": "SDK ↔ harness union", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-11", "cmd": "union --json"},
    {"id": "CUJ-12", "title": "Erase and prove it", "kind": "erase", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-12"},
    {"id": "CUJ-13", "title": "MCP surface drift", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-13", "cmd": "inventory --diff", "cmd2": "agentwatch inventory --diff | grep -qv 'no tool-surface changes'"},
    {"id": "CUJ-14", "title": "\"Did a human approve?\"", "kind": "cli_seed", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUJ-14", "cmd": "search --approval user"},
]

SPEC_TEMPLATE = """# {id} — {title}

**Layer:** {layer} · **LLM:** {llm} · **Requires:** {requires} · **PRD / claim:** {prd}

## Goal
{title}. See `docs/field-test/v0.1.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/{id}.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/{id}.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.1.0/results/<UTC-ts>/cases/{id}/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
"""

_PRE = "ft_up_recorder\nft_start_daemon\n"

STEP_TEMPLATES: dict[str, str] = {
    "recorder_smoke": _PRE + """ft_emit --corpus secrets
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "session-present" "agentwatch sessions | grep -q ft04"
ft_capture_store
ft_finalize
""",
    "recorder_replay": _PRE + """ft_emit --corpus secrets
ft_assert_recorder "replay" "agentwatch replay ft04 | grep -q Bash"
ft_capture_store
ft_finalize
""",
    "redaction": _PRE + """ft_emit --corpus secrets
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "verify-privacy" "agentwatch verify-privacy"
ft_assert_recorder "no-api-key-leak" "! grep -q 'sk-abcdefghijklmnop' /data/agentwatch/records.jsonl"
ft_assert_recorder "no-card-leak" "! grep -q '4111 1111 1111 1111' /data/agentwatch/records.jsonl"
ft_assert_recorder "secret-detected" "grep -q secret-detected /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
""",
    "tamper": _PRE + """ft_emit --corpus secrets
# Corrupt a *record* line (line 1 is the format header; line 3 is seq 1).
ft_recorder bash -lc 'sed -i "3s/./X/" /data/agentwatch/records.jsonl'
ft_assert_recorder "tamper-detected" "! agentwatch verify-store"
ft_assert_recorder "break-at-seq1" "agentwatch verify-store 2>&1 | grep -q 'seq 1'"
ft_capture_store
ft_finalize
""",
    "tamper_repair": _PRE + """ft_emit --corpus secrets
ft_recorder bash -lc 'sed -i "3s/./X/" /data/agentwatch/records.jsonl'
ft_assert_recorder "tamper-detected" "! agentwatch verify-store"
ft_assert_recorder "repair" "agentwatch verify-store --repair --yes"
ft_assert_recorder "chain-green-after-repair" "agentwatch verify-store"
ft_assert_recorder "intact-prefix-kept" "grep -q '\\"seq\\": 0' /data/agentwatch/records.jsonl"
ft_assert_recorder "broken-record-dropped" "! grep -q '\\"seq\\": 1' /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
""",
    "config_bad": """ft_up_recorder
ft_recorder bash -lc 'printf "nope = 1\\n" > /tmp/bad.toml'
ft_assert_recorder "fail-closed" "! agentwatch --config /tmp/bad.toml status"
ft_assert_recorder "config-error-surface" "agentwatch --config /tmp/bad.toml status 2>&1 | grep -q E_CONFIG"
ft_finalize
""",
    "gap": """ft_up_recorder
ft_start_daemon
ft_emit --old
ft_recorder bash -lc 'kill -9 $(cat /data/agentwatch/daemon.pid) || true; rm -f /run/agentwatch/agentwatch.sock; sleep 1'
ft_start_daemon
ft_recorder bash -lc "sleep 3"
ft_assert_recorder "gap-record" "grep -q recording-gap /data/agentwatch/records.jsonl"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
""",
    "spool": """ft_up_recorder
ft_recorder bash -lc 'rm -f /run/agentwatch/agentwatch.sock.spool || true'
# The daemon is deliberately NOT running: emit-hook spools instead of dropping (F1).
ft_emit --corpus secrets
ft_assert_recorder "spooled" "test -s /run/agentwatch/agentwatch.sock.spool"
ft_start_daemon
sleep 2
ft_assert_recorder "replayed-once" "agentwatch verify-store && agentwatch sessions | grep -q ft04"
ft_capture_store
ft_finalize
""",
    "quarantine": """ft_up_recorder
ft_start_daemon
ft_recorder python3 -c "import os,socket; s=socket.socket(socket.AF_UNIX); s.connect(os.environ['AGENTWATCH_SOCKET']); s.sendall(b'{not-json\\n'); s.close()"
sleep 1
ft_assert_recorder "quarantined" "test -s /data/agentwatch/quarantine.jsonl"
ft_assert_recorder "chain-green" "agentwatch verify-store"
ft_capture_store
ft_finalize
""",
    "store_full": """ft_up_recorder
ft_recorder bash -lc 'AGENTWATCH_STORE__MAX_SIZE_MB=1 agentwatch-daemon >/tmp/daemon.log 2>&1 & for i in $(seq 1 50); do [ -S "$AGENTWATCH_SOCKET" ] && break; sleep 0.2; done'
ft_recorder python3 /ft/scripts/run-soak.py --count 6000 --interval 0.001 || true
ft_assert_recorder "stopped-and-surfaced" "agentwatch status | grep -qi stopped"
ft_capture_store
ft_finalize
""",
    "otel_export": """ft_record "compose up recorder jaeger otel-collector"
"${STACK_COMPOSE[@]}" up -d --build recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
sleep 5
ft_assert_recorder "jaeger-services" "curl -sf http://jaeger:16686/api/services | grep -q agentwatch"
ft_capture_store_soft
ft_finalize
""",
    "otel_export_down": """ft_record "compose up recorder jaeger otel-collector"
"${STACK_COMPOSE[@]}" up -d --build recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
# Endpoint down must not break the agent (exit 0), then recover to a live endpoint.
ft_assert_recorder "endpoint-down-nonfatal" "python3 /ft/scripts/otel-probe.py --endpoint http://127.0.0.1:9 --service agentwatch"
ft_assert_recorder "recover" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
sleep 5
ft_assert_recorder "delivered-after-recovery" "curl -sf http://jaeger:16686/api/services | grep -q agentwatch"
ft_capture_store_soft
ft_finalize
""",
    "selftest_gate": """ft_up_recorder
ft_assert_recorder "export-blocked" "! agentwatch --set export.enabled=true --set redaction.self_test=disabled status"
ft_finalize
""",
    "clock_skew": _PRE + """ft_emit --future
ft_assert_recorder "degraded-clock-skew" "curl -sf http://127.0.0.1:9100/healthz | grep -q clock-skew"
ft_capture_store
ft_finalize
""",
    "partial_session": _PRE + """ft_emit --corpus partial --session ft-partial
ft_assert_recorder "replay" "agentwatch replay ft-partial | grep -q Bash"
ft_assert_recorder "sessions" "agentwatch sessions | grep -q ft-partial"
ft_capture_store
ft_finalize
""",
    "health": _PRE + """ft_assert_recorder "states-recording" "curl -sf http://127.0.0.1:9100/healthz | grep -q '\\"state\\": \\"recording\\"'"
ft_assert_recorder "status-matches" "agentwatch status | grep -q 'state: recording'"
ft_capture_store
ft_finalize
""",
    "metrics": _PRE + """ft_assert_recorder "healthz-contract" "python3 -c \\"import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:9100/healthz')); assert {'state','reason','store','export','redaction','hooks','gaps'} <= set(d)\\""
ft_capture_store
ft_finalize
""",
    "soak": _PRE + """ft_assert_recorder "soak" "python3 /ft/scripts/run-soak.py --count {count} --interval {interval} --min-delivery {min}"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
""",
    "demo": """ft_up_recorder
ft_assert_recorder "demo" "agentwatch demo --json >/dev/null"
ft_assert_recorder "purge" "agentwatch demo --purge --json >/dev/null"
ft_capture_store
ft_finalize
""",
    "checkpoint": _PRE + """ft_emit --corpus secrets
ft_assert_recorder "export-signed" "agentwatch checkpoint export --sign --output /tmp/cp.json && test -s /tmp/cp.json"
ft_assert_recorder "derive-pubkey" "python3 -c \\"from agentwatch.signing import key_from_private; import pathlib; pathlib.Path('/tmp/cp.pub').write_bytes(key_from_private(pathlib.Path('/data/agentwatch/signing.key').read_bytes()).public_bytes)\\""
ft_assert_recorder "verify-ok" "agentwatch checkpoint verify /tmp/cp.json --public-key /tmp/cp.pub --json | grep -q '\\"ok\\": true'"
ft_capture_store
ft_finalize
""",
    "posture": _PRE + """ft_emit --corpus secrets
ft_assert_recorder "dir-0700" '[ "$(stat -c %a /data/agentwatch)" = 700 ]'
ft_assert_recorder "records-0600" '[ "$(stat -c %a /data/agentwatch/records.jsonl)" = 600 ]'
ft_capture_store
ft_finalize
""",
    "fidelity": """ft_up_recorder
for mode in metadata-only truncated hashed full; do
  d="/data/agentwatch-$mode"
  ft_recorder bash -lc "AGENTWATCH_STORE__PATH=$d AGENTWATCH_PRIVACY__MODE=$mode AGENTWATCH_SOCKET=/run/agentwatch/$mode.sock agentwatch-daemon >/tmp/daemon-$mode.log 2>&1 & for i in \\$(seq 1 50); do [ -S /run/agentwatch/$mode.sock ] && break; sleep 0.2; done"
  ft_recorder bash -lc "AGENTWATCH_SOCKET=/run/agentwatch/$mode.sock python3 /ft/scripts/emit-hook.py --corpus secrets" || true
  ft_assert_recorder "mode-$mode" "grep -q '\\"privacy_mode\\": \\"$mode\\"' $d/records.jsonl"
  ft_recorder bash -lc "pkill -f agentwatch-daemon || true; sleep 0.3"
done
ft_capture_store_soft
ft_finalize
""",
    "offline": """ft_record "build recorder image"
"${STACK_COMPOSE[@]}" build recorder >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
# No network namespace: the recorder must run record -> verify entirely offline.
ft_assert "offline-record-verify" docker run --rm --network none agentwatch-fieldtest-recorder:local bash -lc 'agentwatch --set store.path=/data demo --json >/dev/null && agentwatch --set store.path=/data verify-store'
ft_finalize
""",
    "portability": """venv="$FT_CASE_DIR/artifacts/venv"
ft_record "host venv + native agentwatch"
ft_run python3 -m venv "$venv"
ft_run "$venv/bin/pip" install -q -e "$REPO_ROOT/packages/python-sdk"
ft_assert "host-native-demo" "$venv/bin/agentwatch" --set store.path="$FT_CASE_DIR/artifacts/hoststore" demo --json
ft_finalize
""",
    "conformance": """ft_up_recorder
ft_assert_recorder "adapters-conform" "cd /work/packages/python-sdk && PYTHONPATH=src:tests python3 -c \\"import conformance_registry; from agentwatch import conformance; r=conformance.run_registered(); assert r and all(x.ok for x in r), [x.summary() for x in r]\\""
ft_finalize
""",
    "migrate": """ft_up_recorder
# v0.1.0: store-format migration is a documented not-implemented stub. The honest
# contract is that it fails closed and names the milestone; the store stays readable.
ft_assert_recorder "migrate-not-implemented" "agentwatch --set store.path=/data/agentwatch migrate 2>&1 | grep -q E_NOT_IMPLEMENTED"
ft_assert_recorder "unknown-version-rejected" "! agentwatch --set store.path=/data/agentwatch migrate"
ft_assert_recorder "verify-store" "agentwatch --set store.path=/data/agentwatch verify-store"
ft_finalize
""",
    "cli_seed": """ft_up_recorder
ft_recorder python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl --out /tmp/ft-fixtures
ft_assert_recorder "cli" "agentwatch {cmd} >/dev/null"
{cmd2_line}
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_capture_store
ft_finalize
""",
    "erase": """ft_up_recorder
ft_recorder python3 /ft/scripts/seed-fixtures.py --store /data/agentwatch/records.jsonl
ft_assert_recorder "purge" "agentwatch purge ft-seed-main --reason 'subject request' --yes"
ft_assert_recorder "chain-green" "agentwatch verify-store"
ft_assert_recorder "marker-present" "grep -q session-purge /data/agentwatch/records.jsonl"
ft_assert_recorder "tombstoned" "grep -q '\\"tombstone\\": true' /data/agentwatch/records.jsonl"
ft_assert_recorder "payload-gone" "! grep -q 'make build' /data/agentwatch/records.jsonl"
ft_capture_store
ft_finalize
""",
    "llm": _PRE + """ft_assert_recorder "drive-agent" "python3 /ft/scripts/drive-agent.py --session ft-llm"
ft_assert_recorder "verify-store" "agentwatch verify-store"
ft_assert_recorder "records" "agentwatch sessions | grep -q ft-llm"
ft_assert_recorder "llm-io-captured" "test -s /data/agentwatch/test-llm-io.jsonl"
ft_assert_recorder "llm-response-captured" "grep -q '\\"response\\"' /data/agentwatch/test-llm-io.jsonl"
ft_capture_store
ft_finalize
""",
    "analyst": """ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
# Run the full Playwright suite; the screenshots spec writes the user-guide PNGs
# straight into docs/assets/screenshots so the guide images stay fresh.
mkdir -p "$REPO_ROOT/docs/assets/screenshots" "$FT_CASE_DIR/artifacts/screenshots"
ft_assert "playwright" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright install chromium && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright test"
for name in dashboard-overview dashboard-to-fleet fleet-default timeline-normal timeline-spans anomalies-default anomalies-critical compare-deltas; do
  ft_assert "guide-$name" test -f "$REPO_ROOT/docs/assets/screenshots/$name.png"
done
cp "$REPO_ROOT/docs/assets/screenshots/"*.png "$FT_CASE_DIR/artifacts/screenshots/" 2>/dev/null || true
ft_finalize
""",
    "a11y": """ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
ft_assert "playwright-a11y" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && npx playwright install chromium && npx playwright test tests/e2e/a11y.spec.ts"
ft_finalize
""",
    "playwright_shots": """ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
mkdir -p "$REPO_ROOT/docs/assets/screenshots"
ft_assert "playwright-screenshots" bash -lc "cd '$REPO_ROOT/apps/web' && npm ci --no-audit --no-fund && npx playwright install chromium && FT_SCREENSHOT_DIR='$REPO_ROOT/docs/assets/screenshots' npx playwright test tests/e2e/screenshots.spec.ts"
for name in dashboard-overview dashboard-to-fleet fleet-default timeline-normal timeline-spans anomalies-default anomalies-critical compare-deltas; do
  ft_assert "guide-$name" test -f "$REPO_ROOT/docs/assets/screenshots/$name.png"
done
mkdir -p "$FT_CASE_DIR/artifacts/screenshots"
cp "$REPO_ROOT/docs/assets/screenshots/"*.png "$FT_CASE_DIR/artifacts/screenshots/" 2>/dev/null || true
ft_finalize
""",
    "detector": """ft_up_recorder
ft_run python3 "$REPO_ROOT/scripts/migrate-db.py"
ft_run python3 "$REPO_ROOT/scripts/seed-e2e-data.py"
sleep 5
ft_assert "anomalies-api" bash -lc "curl -sf http://localhost:8100/api/v1/anomalies -o '$FT_CASE_DIR/artifacts/anomalies.json' && python3 -c \\"import json; d=json.load(open('$FT_CASE_DIR/artifacts/anomalies.json')); assert d['data']['items']\\""
# Full detector matrix: all 154 ported scenarios across all 35 rule-based
# detectors (positive must fire, negative must not, escalated = critical).
mkdir -p "$FT_CASE_DIR/artifacts"
ft_assert "detector-full-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json
ft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"
ft_finalize
""",
    "first_run_timing": """ft_assert "first-run-timing" bash -lc "cd '$REPO_ROOT' && python3 scripts/first_run_timing.py"
ft_finalize
""",
    "bulk_corpus": """ft_up_recorder
ft_assert "corpus-validate" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed 2000 '' /artifacts
ft_finalize
""",
    "detector_corpus": """ft_up_recorder
ft_assert "detector-corpus-diagnostic" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed 5000 --diagnose /artifacts
ft_finalize
""",
    "full_corpus": """ft_up_recorder
# Free memory: stop the long-running analytics worker before the heavy one-off run.
"${STACK_COMPOSE[@]}" stop analytics >/dev/null 2>&1 || true
ft_assert "full-corpus-validate" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed shard '' /artifacts
ft_finalize
""",
    "synthetic_llm": """ft_up_recorder
ft_assert "synthetic-1m-llm-pilot" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces2":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics /ft/llm-validation.sh /traces/synthetic 100 /artifacts
ft_finalize
""",
    "llm_validation": """ft_up_recorder
ft_assert "llm-3way-validation" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces2":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics /ft/llm-validation.sh /traces/synthetic 25 /artifacts
ft_finalize
""",
    "cross_framework": """ft_up_recorder
ft_assert "cross-framework-raw-agent" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT":/src -w /src -e OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 recorder -lc "python m13-agents/agent-raw/generate_traces.py"
sleep 5
ft_assert_recorder "cross-framework-visible" "curl -sf http://jaeger:16686/api/services | grep -q m13-raw-agent"
ft_finalize
""",
    "health_selftest": _PRE + """ft_assert_recorder "self-test-in-health" "curl -sf http://127.0.0.1:9100/healthz | grep -q self_test_passing"
ft_finalize
""",
}


def _slug(title: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in title)
    return "-".join(part for part in safe.split("-") if part)[:48]


def _step(case: dict[str, str]) -> str:
    template = STEP_TEMPLATES.get(case["kind"])
    if template is None:
        raise SystemExit(f"unknown kind {case['kind']!r} for {case['id']}")
    cmd2 = case.get("cmd2", "")
    cmd2_line = f'ft_assert_recorder "cli-extra" "{cmd2}"' if cmd2 else ""
    return (
        template.replace("{cmd}", case.get("cmd", ""))
        .replace("{count}", case.get("count", "1000"))
        .replace("{min}", case.get("min", "1.0"))
        .replace("{interval}", case.get("interval", "0.002"))
        .replace("{cmd2_line}", cmd2_line)
    )


def _clean_generated() -> None:
    for path in CASES_DIR.glob("*.md"):
        if path.name not in CUSTOM_SPECS:
            path.unlink()
    for path in STEPS_DIR.glob("*.sh"):
        path.unlink()


def main() -> int:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    STEPS_DIR.mkdir(parents=True, exist_ok=True)
    _clean_generated()
    for case in CASES:
        slug = _slug(case["title"])
        if case.get("spec") != "custom":
            (CASES_DIR / f"{case['id']}-{slug}.md").write_text(
                SPEC_TEMPLATE.format(**case), encoding="utf-8"
            )
        (STEPS_DIR / f"{case['id']}.sh").write_text(_step(case), encoding="utf-8")
    (CASES_DIR / "registry.json").write_text(json.dumps(CASES, indent=2) + "\n", encoding="utf-8")
    print(f"gen_cases: wrote {len(CASES)} specs + {len(CASES)} step scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
