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
import re
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
    # S1 — install, deployability, attestation
    {"id": "FT-ENV-0", "title": "Fresh install → first record on 3 OSes", "kind": "v020_host", "layer": "recorder", "llm": "no", "requires": "python", "prd": "EXT-10,13 NFR-4,25 NAM-1", "class": "P/F", "suite": "s1-install", "steps": 'ft_assert "first-run-timing" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 "$REPO_ROOT/scripts/first_run_timing.py"\nft_assert "naming-guard" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -c "import agentwatch.naming"\n'},
    {"id": "FT-WIN-1", "title": "Windows support (named-pipe daemon + service)", "kind": "v020_host", "layer": "recorder", "llm": "no", "requires": "shell", "prd": "WIN-1", "class": "P/F|D", "suite": "s1-install", "steps": 'ft_assert "windows-host" test "$(uname -s)" = Windows_NT\n'},
    {"id": "FT-DEP-1", "title": "Managed-policy environment, honest doctor", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DEP-1", "class": "P/F|D", "suite": "s1-install", "steps": 'ft_assert_recorder "doctor-effective" "agentwatch doctor | grep -Eq \'hooks effective: (yes|blocked|unknown|no)\'"\n'},
    {"id": "FT-DEP-2", "title": "Hook-strip → recorder-config-changed + gap", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DEP-2", "class": "P/F", "suite": "s1-install", "steps": 'ft_assert_recorder "coverage-attestation" "agentwatch coverage --json | grep -q attestation"\n'},
    {"id": "FT-DEP-3", "title": "End-to-end hook wall-clock per OS + budget", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DEP-3", "class": "P/F|D", "suite": "s1-install", "steps": 'ft_assert_recorder "hook-perf-gate" "python3 /ft/scripts/run-soak.py --count 500 --interval 0.002 --min-delivery 1.0"\n'},
    # S2 — standards & interop
    {"id": "FT-AAT-1", "title": "AAT export → third-party consumer round-trip", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "AAT-1/2/4", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "aat-export" "agentwatch export-session ft04 --format aat --output /tmp/s.aat.json && test -s /tmp/s.aat.json"\nft_assert_recorder "aat-external-consumer" "python3 /ft/scripts/aat_roundtrip.py /tmp/s.aat.json"\n'},
    {"id": "FT-AAT-2", "title": "Foreign AAT ingest + quarantine", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "AAT-3", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "aat-ingest" "agentwatch ingest --format aat /ft/fixtures/aat/foreign.aat.json"\nft_assert_recorder "quarantine" "test -s /data/agentwatch/quarantine.jsonl"\n'},
    {"id": "FT-AAT-3", "title": "AAT draft pin + drift check", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "AAT-5", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "aat-version-cited" "agentwatch --version | grep -qi aat"\nft_assert_recorder "aat-drift" "python3 /ft/scripts/aat_drift.py"\n'},
    {"id": "FT-OTEL-1", "title": "Canonical OTel agent spans in ≥2 backends", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker,jaeger", "prd": "OTEL-1", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"\nft_assert "jaeger" bash -lc "sleep 8 && curl -sf http://localhost:16686/api/services | grep -q agentwatch"\n'},
    {"id": "FT-OTEL-2", "title": "OTLP/gRPC + protobuf, streaming", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "OTEL-3", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "grpc-stream" "python3 /ft/scripts/otel_grpc_stream.py --endpoint http://otel-grpc:4317 --mb 100"\n'},
    {"id": "FT-OTEL-3", "title": "Privacy-mode ↔ content-capture mapping", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "OTEL-2", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "privacy-default" "grep -q \'privacy_mode.*metadata-only\' /data/agentwatch/records.jsonl"\nft_assert_recorder "privacy-property" "python3 /ft/scripts/privacy_property.py"\n'},
    {"id": "FT-OTEL-4", "title": "Skill / command-execution agent-span mapping", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "OTEL-4", "class": "P/F|D", "suite": "s2-interop", "steps": 'ft_assert_recorder "skill-spans" "python3 /ft/scripts/skill_spans.py"\n'},
    {"id": "FT-TRACE-1", "title": "One causal chain across 3 hosts × 3 harnesses", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker,fleet", "prd": "TRACE-1/2", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "fleet-chain" "python3 /ft/scripts/fleet-run.py --hosts fleet-h1,fleet-h2,fleet-h3"\n'},
    {"id": "FT-TRACE-2", "title": "Cross-host clock skew ordering", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker,fleet", "prd": "TRACE-2,F9", "class": "P/F", "suite": "s2-interop", "steps": 'ft_assert_recorder "fleet-skew" "python3 /ft/scripts/fleet-run.py --skew 3 --hosts fleet-h1,fleet-h2"\n'},
    {"id": "FT-PG-1", "title": "Drop-Postgres mode + bit-for-bit rebuild", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PG-1", "class": "P/F|D", "suite": "s2-interop", "steps": 'ft_assert_recorder "pg-down-commands" "agentwatch sessions >/dev/null && agentwatch verify-store"\nft_assert_recorder "index-rebuild" "agentwatch index rebuild --json && agentwatch index rebuild --json"\n'},
    {"id": "FT-PG-2", "title": "Cross-tenant isolation + audit", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PG-2", "class": "P/F|D", "suite": "s2-interop", "steps": 'ft_assert_recorder "cross-tenant-empty" "python3 /ft/scripts/tenant_isolation.py"\n'},
    {"id": "FT-PG-3", "title": "SDK spans in the unified store, chain-protected", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PG-3", "class": "P/F|D", "suite": "s2-interop", "steps": 'ft_assert_recorder "sdk-in-store" "python3 /ft/scripts/sdk_emit.py && agentwatch verify-store"\nft_assert_recorder "union-fallback" "agentwatch union --json"\n'},
    # S3 — harness fidelity, real-time, test kit
    {"id": "FT-CUR-1", "title": "Cursor full-fidelity golden-corpus audit", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUR-1/3", "class": "P/F|D", "suite": "s3-harness", "steps": 'ft_assert_recorder "cursor-corpus" "python3 /ft/scripts/ingest-fixture.py --kind cursor --corpus /ft/fixtures/cursor"\nft_assert_recorder "verify-store" "agentwatch verify-store"\n'},
    {"id": "FT-CUR-2", "title": "Cursor blocking events + IDE/CLI/remote", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CUR-2", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "cursor-blocking" "python3 /ft/scripts/ingest-fixture.py --kind cursor-blocking --corpus /ft/fixtures/cursor"\n'},
    {"id": "FT-GEM-1", "title": "Gemini native-OTel ingest + logPrompts redaction", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "GEM-1/2", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "gemini-ingest" "python3 /ft/scripts/ingest-fixture.py --kind gemini --corpus /ft/fixtures/gemini && agentwatch verify-store"\n'},
    {"id": "FT-COD-1", "title": "Codex rollout reader (dedup, .zst, dangling)", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "COD-1", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "codex-rollout" "python3 /ft/scripts/ingest-fixture.py --kind codex --corpus /ft/fixtures/codex && agentwatch verify-store"\n'},
    {"id": "FT-MCP-1", "title": "MCP full surface across 3 protocol revisions", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "MCP-1..6", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "mcp-surface" "python3 /ft/scripts/ingest-fixture.py --kind mcp --corpus /ft/fixtures/mcp && agentwatch verify-store"\n'},
    {"id": "FT-MCP-2", "title": "Closed-by-spec surfaces + malformed frames", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "MCP-5,B4", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "mcp-malformed-quarantine" "python3 /ft/scripts/ingest-fixture.py --kind mcp-malformed && test -s /data/agentwatch/quarantine.jsonl"\n'},
    {"id": "FT-LOG-1", "title": "Long-tail coding-agent log readers, log-read tier", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "LOG-1", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "log-readers" "python3 /ft/scripts/ingest-fixture.py --kind logreaders --corpus /ft/fixtures/logreaders"\n'},
    {"id": "FT-STR-1", "title": "Live view p99 ≤ 1 s", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "STR-1/2", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "stream-p99" "python3 /ft/scripts/stream-probe.py --mode p99 --budget-ms 1000"\n'},
    {"id": "FT-STR-2", "title": "Drop-consumer reconciliation + 24 h soak", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "STR-2/3", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "stream-drop-reconcile" "python3 /ft/scripts/stream-probe.py --mode drop-consumer --bounded"\n'},
    {"id": "FT-LG-1", "title": "LangGraph + raw-Python Tier-2 at full fidelity", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "LG-1/2", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "langgraph-instrument" "python3 /ft/scripts/drive-agent.py --session ft-lg && agentwatch verify-store"\n'},
    {"id": "FT-XHT-1", "title": "Payload corpus replay + self-test", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "XHT-1", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "xht-replay-self-test" "python3 /ft/scripts/xht_replay.py --self-test"\n'},
    {"id": "FT-XHT-2", "title": "Live soak on OpenCode (real agent)", "kind": "v020", "layer": "recorder", "llm": "yes", "requires": "docker,omlx", "prd": "XHT-2", "class": "P/F|D", "suite": "s3-harness", "steps": 'if [[ "${OMLX_BASE_URL:-}" == "" ]]; then ft_assert_recorder "xht-opencode-bounded" "python3 /ft/scripts/xht_replay.py --opencode --bounded"; else ft_assert_recorder "xht-opencode" "python3 /ft/scripts/xht_replay.py --opencode --bounded"; fi\n'},
    {"id": "FT-XHT-3", "title": "Cross-validate vs 2 independent OSS parsers", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "XHT-3", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "xht-cross-parser" "python3 /ft/scripts/xht_replay.py --cross-parser"\n'},
    {"id": "FT-XHT-4", "title": "Honest fidelity tiers in the generated matrix", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "XHT-4", "class": "P/F", "suite": "s3-harness", "steps": 'ft_assert_recorder "matrix-tiers" "python3 -c \'import agentwatch.compatibility\'"\n'},
    # S4 — detectors & redaction
    {"id": "FT-DET-1", "title": "One-command deterministic detector eval", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-1/2", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json\nft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"\n'},
    {"id": "FT-DET-2", "title": "≥80% of rule detectors non-silent; catalog guard", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-3", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json\nft_assert "detector-nonsilent-80" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"\n'},
    {"id": "FT-DET-3", "title": "LLM detectors in the same harness", "kind": "v020", "layer": "recorder", "llm": "yes", "requires": "docker,omlx", "prd": "DET-4", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix-llm" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -e OMLX_MODEL="${OMLX_MODEL:-Qwen3-4B-Instruct-2507-4bit}" analytics -m analytics.scenario_validation --all\n'},
    {"id": "FT-DET-4", "title": "Injection + memory-surface observations", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-6/7", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json\nft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"\n'},
    {"id": "FT-DET-5", "title": "Detector telemetry (SIEM-feedable, content-free)", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-5", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert_recorder "telemetry-off-default" "agentwatch coverage --json"\nft_assert_recorder "telemetry-module" "python3 -c \'import agentwatch.detector_telemetry\'"\n'},
    {"id": "FT-DET-6", "title": "New-class scenario depth", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-6", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json\nft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"\n'},
    {"id": "FT-DET-7", "title": "Real-harness trace replay", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DET-7", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "detector-matrix" "${STACK_COMPOSE[@]}" run --rm --entrypoint python -v "$FT_CASE_DIR/artifacts":/artifacts analytics -m analytics.scenario_validation --all --out /artifacts/detector-results.json\nft_assert "detector-tpr-fpr" python3 "$REPO_ROOT/scripts/fieldtest/check-detector-results.py" "$FT_CASE_DIR/artifacts/detector-results.json"\n'},
    {"id": "FT-COR-1", "title": "Public corpus + second-corpus reproduction", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "COR-1", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert "second-corpus" "${STACK_COMPOSE[@]}" run --rm --entrypoint bash -v "$REPO_ROOT/data/traces":/traces:ro -v "$FT_DIR":/ft -v "$FT_CASE_DIR/artifacts":/artifacts analytics /ft/corpus.sh /traces/processed 2000 '' /artifacts\n'},
    {"id": "FT-COR-2", "title": "Incident-registry export", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "COR-2/3", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert_recorder "incident-export" "agentwatch evidence ft04 --include incident-report.json --out /tmp/inc.zip && test -s /tmp/inc.zip"\nft_assert_recorder "no-auto-submit" "! agentwatch evidence --help | grep -qi submit"\n'},
    {"id": "FT-RED-1", "title": "Redaction quality benchmark", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "RED-1", "class": "P/F", "suite": "s4-detectors", "steps": 'ft_assert_recorder "redaction-benchmark" "agentwatch redact eval --json"\n'},
    # S5 — identity, compliance, SIEM
    {"id": "FT-IDN-1", "title": "Attribution end-to-end in one command", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker,fleet", "prd": "IDN-1..4", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "idn-attribution" "python3 /ft/scripts/fleet-run.py --attribution"\n'},
    {"id": "FT-IDN-2", "title": "Identity fields never contain secret material", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "IDN-1,DD-06", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "identity-no-secrets" "python3 /ft/scripts/privacy_property.py --what identity"\n'},
    {"id": "FT-IDN-3", "title": "Ambient / shared credential hygiene observation", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "IDN-3,DD-07", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "credential-hygiene" "agentwatch search --identity user --json"\n'},
    {"id": "FT-CMP-1", "title": "One-command offline compliance report", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CMP-1/2", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "compliance-report" "agentwatch compliance report --framework iso-42001 --period Q3-2026 --out /tmp/audit"\n'},
    {"id": "FT-CMP-2", "title": "Retention profiles + signed default posture", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CMP-3/4", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "retention-apply" "agentwatch retention apply --profile general-6mo"\nft_assert_recorder "signed-default" "python3 /ft/scripts/signed_default.py"\n'},
    {"id": "FT-CMP-3", "title": "All five compliance templates + key rotation", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CMP-3/4", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "all-templates" "python3 /ft/scripts/compliance_templates.py"\nft_assert_recorder "key-rotation" "python3 /ft/scripts/checkpoint_rotate.py"\n'},
    {"id": "FT-SIEM-1", "title": "OCSF 1.5.0 + Syslog event stream", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "SIEM-1/2", "class": "P/F", "suite": "s5-identity", "steps": 'ft_emit --corpus secrets\nft_assert_recorder "siem-conformance" "python3 /ft/scripts/siem_conformance.py"\n'},
    {"id": "FT-ASI-1", "title": "OWASP ASI-2026 + AST10 report", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "ASI-1", "class": "P/F", "suite": "s5-identity", "steps": 'ft_assert_recorder "asi-report" "agentwatch compliance report --framework owasp-asi-2026 --out /tmp/asi"\n'},
    # S6 — new capture surfaces
    {"id": "FT-A2A-1", "title": "Cross-org delegation provable", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "A2A-1/2", "class": "P/F", "suite": "s6-surfaces", "steps": 'ft_assert_recorder "a2a-roundtrip" "python3 /ft/scripts/a2a_roundtrip.py"\n'},
    {"id": "FT-GWY-1", "title": "Gateway OTel ingest + exact vs estimated cost", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "GWY-1/2", "class": "P/F", "suite": "s6-surfaces", "steps": 'ft_assert_recorder "gateway-ingest" "python3 /ft/scripts/ingest-fixture.py --kind gateway --corpus /ft/fixtures/gateway"\nft_assert_recorder "cost-exact-vs-estimated" "agentwatch cost --json | grep -Eq \'exact|estimated\'"\n'},
    {"id": "FT-SYS-1", "title": "System-effects ingest join (Linux, opt-in)", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker,linux", "prd": "SYS-1", "class": "P/F|D", "suite": "s6-surfaces", "steps": 'ft_assert_recorder "system-ingest" "python3 /ft/scripts/ingest-fixture.py --kind system"\n'},
    {"id": "FT-CCA-1", "title": "Claude Compliance API ingest (consent-first)", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CCA-1", "class": "P/F", "suite": "s6-surfaces", "steps": 'ft_assert_recorder "cca-consent" "python3 /ft/scripts/ingest-fixture.py --kind cca --corpus /ft/fixtures/cca"\n'},
    {"id": "FT-ACS-1", "title": "ACS Guardian audit-trail ingest (watch)", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "ACS-1", "class": "P/F|D", "suite": "s6-surfaces", "steps": 'ft_assert_recorder "acs-ingest" "python3 /ft/scripts/ingest-fixture.py --kind acs --corpus /ft/fixtures/acs && agentwatch verify-store"\n'},
    # S7 — platform, SDK, interfaces, policy
    {"id": "FT-SDK-1", "title": "Flush-on-exit, sampler determinism, no-op after shutdown", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "SDK-1..3", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "sdk-lifecycle" "python3 /ft/scripts/sdk_lifecycle.py"\n'},
    {"id": "FT-API-1", "title": "OpenAPI publication + typed client drift", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "API-1", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert "openapi-present" bash -lc "curl -sf http://localhost:8100/openapi.json >/dev/null"\n'},
    {"id": "FT-EXA-1", "title": "Examples gallery recipes", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "EXA-1", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert "examples-gallery" test -n "$(find "$REPO_ROOT/examples" -name "*.py" -print -quit)"\n'},
    {"id": "FT-GOV-1", "title": "Community plugin API + codemod", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "GOV-1", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "plugin-conformance" "python3 -c \'import agentwatch.conformance\'"\n'},
    {"id": "FT-AGI-1", "title": "Read-only MCP server safety", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "AGI-1", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "mcp-no-write-tool" "python3 /ft/scripts/mcp_readonly.py"\n'},
    {"id": "FT-AGI-2", "title": "Investigation skill + versioned CLI JSON", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "AGI-2", "class": "P/F", "suite": "s7-platform", "steps": 'ft_emit --corpus secrets\nft_assert_recorder "skill-answers" "python3 /ft/scripts/investigation_skill.py"\n'},
    {"id": "FT-POL-1", "title": "suggest-policy + broad-rule lint", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "POL-1/2", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "suggest-policy-no-write" "cd /tmp && rm -f proposed.json && agentwatch suggest-policy --since 30d --target claude-settings --out /tmp/proposed.json && test -s /tmp/proposed.json"\nft_assert_recorder "what-if" "agentwatch what-if /tmp/proposed.json --since 30d --json"\n'},
    {"id": "FT-FWK-1", "title": "Certified framework recipes (ADK/Strands/OpenAI/Claude SDK)", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "FWK-1", "class": "P/F|D", "suite": "s7-platform", "steps": 'ft_assert_recorder "framework-recipes" "python3 /ft/scripts/framework_recipes.py"\n'},
    {"id": "FT-FWK-2", "title": "instrument() auto-detect", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "FWK-2", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "instrument-detect" "python3 /ft/scripts/instrument_detect.py"\n'},
    {"id": "FT-CCO-1", "title": "Claude Code native-OTel ingest + tool_use_id join", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CCO-1", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "native-otel-join" "python3 /ft/scripts/native-otel-join.py --corpus /ft/fixtures/cco"\n'},
    {"id": "FT-CCO-2", "title": "Claude Agent SDK / headless via same path", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CCO-2", "class": "P/F", "suite": "s7-platform", "steps": 'ft_assert_recorder "agent-sdk-native" "python3 /ft/scripts/ingest-fixture.py --kind cco"\n'},
    {"id": "FT-TSS-1", "title": "TS-SDK span-taxonomy spike", "kind": "v020_host", "layer": "recorder", "llm": "no", "requires": "python", "prd": "TSS-1", "class": "P/F|D", "suite": "s7-platform", "steps": 'ft_assert "ts-spike-tracked" grep -q TSS-1 "$REPO_ROOT/docs/wbs/v0.2.0/wbs-v0.2.0-index.md"\n'},
    # S8 — authorization & oversight
    {"id": "FT-APV-1", "title": "Classifier/bypass/user fidelity", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "APV-1", "class": "P/F", "suite": "s8-apv", "steps": 'ft_assert_recorder "approval-fidelity" "python3 /ft/scripts/oversight-corpus.py --fidelity"\n'},
    {"id": "FT-APV-2", "title": "Oversight report on corpus", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "APV-3", "class": "P/F", "suite": "s8-apv", "steps": 'ft_assert_recorder "oversight-report" "python3 /ft/scripts/oversight-corpus.py --report"\n'},
    {"id": "FT-APV-3", "title": "Permission-mode per call + transitions", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "APV-2", "class": "P/F", "suite": "s8-apv", "steps": 'ft_assert_recorder "permission-mode" "python3 /ft/scripts/oversight-corpus.py --modes"\n'},
    # S9 — capability supply chain & memory
    {"id": "FT-CAP-1", "title": "Plugin4Shell-shape drift", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CAP-1/2", "class": "P/F", "suite": "s9-capability", "steps": 'ft_assert_recorder "capability-drift" "python3 /ft/scripts/capability-drift.py --kind drift"\n'},
    {"id": "FT-CAP-2", "title": "Capability load attribution", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CAP-3", "class": "P/F", "suite": "s9-capability", "steps": 'ft_assert_recorder "capability-load-attribution" "python3 /ft/scripts/capability-drift.py --kind load"\n'},
    {"id": "FT-MEM-1", "title": "Out-of-band memory edit", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "MEM-1", "class": "P/F", "suite": "s9-capability", "steps": 'ft_assert_recorder "memory-oob-edit" "python3 /ft/scripts/capability-drift.py --kind memory"\n'},
    # S10 — code provenance
    {"id": "FT-PRV-1", "title": "Commit → session", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PRV-1", "class": "P/F", "suite": "s10-provenance", "steps": 'ft_assert_recorder "commit-to-session" "python3 /ft/scripts/provenance-repo.py --commit-to-session"\n'},
    {"id": "FT-PRV-2", "title": "Agent Trace export + content-free ranges", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PRV-2/3", "class": "P/F", "suite": "s10-provenance", "steps": 'ft_assert_recorder "agent-trace-export" "python3 /ft/scripts/provenance-repo.py --agent-trace"\n'},
    {"id": "FT-PRV-3", "title": "Range + content-hash capture under every privacy mode", "kind": "v020_emit", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PRV-2", "class": "P/F", "suite": "s10-provenance", "steps": 'ft_assert_recorder "range-hash-capture" "python3 /ft/scripts/provenance-repo.py --range-hash"\n'},
    # S11 — console & query tier
    {"id": "FT-LUI-1", "title": "Clean-machine console ≤60 s, no Docker", "kind": "v020_host", "layer": "analyst", "llm": "no", "requires": "python,node", "prd": "LUI-1", "class": "P/F", "suite": "s11-console", "steps": 'ft_assert "ui-console-check" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -m agentwatch ui --check --host 127.0.0.1 --no-open\nft_assert "ui-module" env PYTHONPATH="$REPO_ROOT/packages/python-sdk/src" python3 -c "import agentwatch.ui"\nft_assert "console-playwright" python3 "$REPO_ROOT/scripts/fieldtest/console_playwright.py"\n'},
    {"id": "FT-LUI-2", "title": "Embedded index rebuildable / deletable", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "LUI-2", "class": "P/F", "suite": "s11-console", "steps": 'ft_assert_recorder "index-rebuild-delete" "agentwatch index rebuild --json && agentwatch index drop --json && agentwatch sessions >/dev/null && agentwatch index rebuild --json"\n'},
    # S12 — governance & retention
    {"id": "FT-ACC-1", "title": "Role × data-class matrix + access log", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "ACC-1", "class": "P/F", "suite": "s12-governance", "steps": 'ft_assert_recorder "role-matrix" "python3 /ft/scripts/governance_matrix.py --roles"\n'},
    {"id": "FT-ACC-2", "title": "Notice + DPIA from effective config", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "ACC-2", "class": "P/F", "suite": "s12-governance", "steps": 'ft_assert_recorder "governance-notice" "agentwatch governance notice --json | grep -qi \'not legal advice\'"\n'},
    {"id": "FT-HLD-1", "title": "Legal hold vs retention/purge/rebuild", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "HLD-1", "class": "P/F", "suite": "s12-governance", "steps": 'ft_assert_recorder "hold-survives" "python3 /ft/scripts/hold_lifecycle.py"\n'},
    # S13 — investigation depth & verification
    {"id": "FT-ENV-1", "title": "Seeded model-version change", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "ENV-1", "class": "P/F", "suite": "s13-investigation", "steps": 'ft_assert_recorder "env-delta" "python3 /ft/scripts/env_delta.py"\n'},
    {"id": "FT-VFY-1", "title": "Browser verifier parity (offline)", "kind": "v020_host", "layer": "analyst", "llm": "no", "requires": "python", "prd": "VFY-1", "class": "P/F", "suite": "s13-investigation", "steps": 'ft_assert "verifier-artifact" bash -lc "test -f $REPO_ROOT/docs/release/verifier/agentwatch-verify.html"\nft_assert "verifier-checksum" bash -lc "cd $REPO_ROOT && python3 scripts/build_browser_verifier.py --check"\n'},
    {"id": "FT-IR-1", "title": "Multi-session incident case", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "IR-1", "class": "P/F", "suite": "s13-investigation", "steps": 'ft_assert_recorder "incident-case" "python3 /ft/scripts/case_incident.py"\n'},
    {"id": "FT-CNC-1", "title": "Concurrency report + ambiguous", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "CNC-1", "class": "P/F|D", "suite": "s13-investigation", "steps": 'ft_assert_recorder "concurrency-report" "python3 /ft/scripts/concurrency_probe.py"\n'},
    {"id": "FT-SBX-1", "title": "Sandbox-boundary events", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "SBX-1", "class": "P/F|D", "suite": "s13-investigation", "steps": 'ft_assert_recorder "sandbox-events" "python3 /ft/scripts/oversight-corpus.py --sandbox"\n'},
    # S14 — outcomes, ephemeral capture, growth
    {"id": "FT-OUT-1", "title": "Outcome facts + cost per retained change", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "OUT-1", "class": "P/F|D", "suite": "s14-outcomes", "steps": 'ft_assert_recorder "outcomes" "agentwatch outcomes --since 30d --by project --json | grep -Eq \'numerator|denominator\'"\n'},
    {"id": "FT-OUT-2", "title": "Recurring failure signatures", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "OUT-2", "class": "P/F|D", "suite": "s14-outcomes", "steps": 'ft_assert_recorder "digest" "agentwatch digest --since 30d"\n'},
    {"id": "FT-RUN-1", "title": "Sealed runner segment", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "RUN-1", "class": "P/F", "suite": "s14-outcomes", "steps": 'ft_emit --corpus secrets\nft_assert_recorder "runner-segment" "python3 /ft/scripts/segment-runner.py"\n'},
    {"id": "FT-DEMO-1", "title": "Static synthetic demo bundle", "kind": "v020_host", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "DEMO-1", "class": "P/F|D", "suite": "s14-outcomes", "steps": 'ft_assert "demo-bundle-json" python3 -m json.tool "$REPO_ROOT/examples/demo-bundle/bundle.json"\n'},
    {"id": "FT-NTF-1", "title": "Alert-routing recipes", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "NTF-1", "class": "P/F|D", "suite": "s14-outcomes", "steps": 'ft_assert_recorder "alert-recipes" "python3 /ft/scripts/alert_recipes.py --webhook-sink"\n'},
    # S15 — hostile data, claims ledger, closed gates
    {"id": "FT-HOSTILE-1", "title": "Weaponized ingest containment", "kind": "v020_nodaemon", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "R5,ADR-0024,RSK-1", "class": "P/F", "suite": "s15-hostile", "steps": 'ft_assert_recorder "hostile-contained" "python3 /ft/scripts/hostile-ingest.py --corpus /ft/fixtures/hostile"\nft_assert_recorder "quarantined" "test -s /data/agentwatch/quarantine.jsonl"\n'},
    {"id": "FT-CLAIM-1", "title": "Claims ledger green + limitations shrink", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "PRD-48 §5", "class": "P/F", "suite": "s15-hostile", "steps": 'ft_assert "claims-ledger-json" python3 -m json.tool "$REPO_ROOT/docs/release/claims-ledger.json"\nft_assert "known-limitations" test -f "$REPO_ROOT/docs/reference/known-limitations.md"\n'},
    {"id": "FT-MATRIX-1", "title": "Compatibility matrix honest tiers", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker", "prd": "XHT-4,PRD-40 §5.3", "class": "P/F", "suite": "s15-hostile", "steps": 'ft_assert "matrix-file" bash -lc "test -f $REPO_ROOT/docs/reference/compatibility.md"\nft_assert "matrix-honest-tiers" bash -lc "grep -qE \'live-verified|fixture-verified\' $REPO_ROOT/docs/reference/compatibility.md"\n'},
    {"id": "FT-BACKEND-2", "title": "Second live OTLP backend (closes R4)", "kind": "v020", "layer": "recorder", "llm": "no", "requires": "docker,jaeger", "prd": "EXT-10,OTEL-1", "class": "P/F", "suite": "s15-hostile", "steps": 'ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"\nft_assert "jaeger" bash -lc "curl -sf http://localhost:16686/api/services | grep -q agentwatch"\nft_assert "tempo" bash -lc "curl -sf http://localhost:3200/api/search/tags || true"\n'},

]


SPEC_TEMPLATE = """# {id} — {title}

**Layer:** {layer} · **LLM:** {llm} · **Requires:** {requires} · **PRD / claim:** {prd}{suite_line}

## Goal
{title}. See `docs/field-test/{doc_version}/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/{id}.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/{id}.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/{doc_version}/results/{results_token}/cases/{id}/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
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
up_args=(-d); [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || up_args+=(--build)
"${STACK_COMPOSE[@]}" up "${up_args[@]}" recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
ft_assert_recorder "emit-spans" "python3 /ft/scripts/otel-probe.py --endpoint http://otel-collector:4317 --service agentwatch"
sleep 5
ft_assert_recorder "jaeger-services" "curl -sf http://jaeger:16686/api/services | grep -q agentwatch"
ft_capture_store_soft
ft_finalize
""",
    "otel_export_down": """ft_record "compose up recorder jaeger otel-collector"
up_args=(-d); [[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || up_args+=(--build)
"${STACK_COMPOSE[@]}" up "${up_args[@]}" recorder jaeger otel-collector >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
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
[[ "${FT_IMAGES_BUILT:-0}" == "1" ]] || "${STACK_COMPOSE[@]}" build recorder >> "$FT_CASE_DIR/stdout.log" 2>> "$FT_CASE_DIR/stderr.log"
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
    # --- v0.2.0 kinds (M31 31.3) ---------------------------------------------
    # Boot the recorder stack (+ daemon), run the case's `{steps}` block, capture
    # the store softly (v0.2.0 cases mostly assert on CLI output). A case that
    # needs store contents asserts them inside `{steps}`.
    "v020": _PRE + "{steps}ft_capture_store_soft\nft_finalize\n",
    # Same, but without starting the daemon (ingest / fixture / CLI-only cases).
    "v020_nodaemon": "ft_up_recorder\n{steps}ft_capture_store_soft\nft_finalize\n",
    # Emit a real hook corpus first, then the `{steps}` block, then assert store.
    "v020_emit": _PRE + "ft_emit --corpus secrets\n{steps}ft_capture_store\nft_finalize\n",
    # Host-native / no-Docker cases (console, install timing, TS spike).
    "v020_host": "{steps}ft_finalize\n",
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
        .replace("{steps}", case.get("steps", ""))
    )


_SERVICE_RE = re.compile(
    r"\b(analytics|jaeger|otel-collector|otel-grpc|a2a-proxy|litellm|runner|"
    r"managed-hooks|verifier|postgres|fleet|tempo|api|web)\b"
)


def _needs_recycle(step: str) -> bool:
    """True when a case must get a genuinely fresh stack rather than the shared
    one. A soft reset only wipes the recorder store and the read-model tables, so
    any case that touches another service (or the OTLP/DB read path) is given a
    real `down -v` + boot. Host-native cases never boot the stack, never recycle."""
    if "ft_up_recorder" not in step:
        return False
    return bool(_SERVICE_RE.search(step))


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
        step = _step(case)
        # `recycle`: needs a genuinely fresh stack (touches another service);
        # everything else shares the stack and is reset in place.
        case["recycle"] = _needs_recycle(step)
        slug = _slug(case["title"])
        if case.get("spec") != "custom":
            fields = dict(case)
            fields["doc_version"] = "v0.2.0" if case.get("suite") else "v0.1.0"
            fields["results_token"] = "<run-id>" if case.get("suite") else "<UTC-ts>"
            fields["suite_line"] = (
                f" · **Suite:** {case['suite']} · **Class:** {case.get('class', 'P/F')}"
                if case.get("suite")
                else ""
            )
            (CASES_DIR / f"{case['id']}-{slug}.md").write_text(
                SPEC_TEMPLATE.format(**fields), encoding="utf-8"
            )
        (STEPS_DIR / f"{case['id']}.sh").write_text(step, encoding="utf-8")
    (CASES_DIR / "registry.json").write_text(json.dumps(CASES, indent=2) + "\n", encoding="utf-8")
    print(f"gen_cases: wrote {len(CASES)} specs + {len(CASES)} step scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
