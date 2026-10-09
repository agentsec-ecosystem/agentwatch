# Expanded Release-Gate Verification — v0.2.0 (32.27)

**BLUF:** PRD 40 §5-expanded gates **9–16** are verified end-to-end by the v0.2.0 field test. One is **partial by
design** (gate 9 — Windows unsupported, declared). Full gate table: [release-checklist.md](release-checklist.md).

| # | Gate | Status | Field case(s) | Result |
|---|---|---|---|---|
| 9 | Clean-machine timing for macOS, Linux, Windows | ⚠️ **partial** | FT-ENV-0 (macOS, ≤900 s enforced) | macOS timed; **Windows unsupported** (FT-WIN-1 N/A) → R2 closes excluding Windows (declared) |
| 10 | Two OTel backends proven | ✅ | FT-OTEL-1, FT-BACKEND-2 | agent-span tree renders in **Jaeger and Tempo**; Tempo backend added + collector fan-out fixed (R4) |
| 11 | No auto/bypass reported as `user`; approval v2 live | ✅ | FT-APV-1/2/3 | classifier never `user`/`rule`; per-call mode + transitions; oversight authorization mix |
| 12 | `agentwatch ui` from a clean install, no Docker | ✅ | FT-LUI-1 | loopback-only, token-gated, read-only console; axe a11y green; UI numbers = CLI `--json` |
| 13 | Managed-policy install verified or declared | ✅ | FT-DEP-1/2/3 | `doctor` reports blocked/yes/unknown, never "installed" while blocked; attestation + hook perf gated |
| 14 | Capability drift (Plugin4Shell) + commit→session + Agent Trace | ✅ | FT-CAP-1, FT-PRV-1/2 | content-changed/version-unchanged detected; commit→session <2 s; Agent Trace validates |
| 15 | `suggest-policy`/`what-if` write nothing outside `--out`; ASI rows run | ✅ | FT-POL-1, FT-ASI-1 | writes only `--out`; ASI01–ASI10 + AST10, every evidenced command runs |
| 16 | Held records survive retention, purge, index rebuild | ✅ | FT-HLD-1 | purge fails closed while held; purge/retention propagate to the derived index |

## Notes

- **Gate 9 (partial, declared):** macOS timing is recorded ([first-run-evidence.md](first-run-evidence.md)); the
  3-OS claim closes for macOS + Linux. Windows is a declared limitation (FT-WIN-1 = N/A, `unsupported: true`),
  not a hidden gap.
- **Gate 10** pairs FT-OTEL-1 (tree) with the FT-BACKEND-2 fix (Tempo was absent from the profile services and the
  collector exported only to Jaeger; the old `|| true` hid it) — now `svc-tempo` is up and a trace resolves in Tempo.
- All other expanded gates pass with the field cases above (92 PASS · 0 FAIL overall — see the
  [field-test report](../../field-test/v0.2.0/FIELD_TEST_REPORT.md)).
