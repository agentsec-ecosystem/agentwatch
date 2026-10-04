# agentwatch v0.1.0 — Release Notes

Status: **released** — tagged `v0.1.0`. See "Release actions" below for the remaining predecessor step.

## Highlights

- **Records every Claude Code tool call** in OpenTelemetry GenAI format, redacted by default.
- **Local-first**, hash-chained JSONL store; opt-in OTLP export gated on a redaction self-test.
- **Open security-event schema** (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`,
  `drift-detected`) published in `schema/`.
- **Session replay** and **replay-as-code** (`agentwatch export-session <id> --format ndjson`) with the
  chain segment, for agentdrill/CI.
- **Harness breadth**: Claude Code (full) + provisional modeled Cursor / Codex CLI / Gemini CLI / CrewAI /
  PydanticAI adapters; MCP interposition proxy (stdio + HTTP/SSE).
- **Fleet + drift** (R13): opt-in multi-host aggregation and trailing-baseline drift signals with
  deployment correlation.
- **Resilience**: adaptive durability, chain checkpoints, continuous verification, `verify-store --repair`,
  clock-skew flagging, rotated logs, `init --service`, fault-injection F1–F10.

## Install

```sh
npx @agentsec-ecosystem/cli init      # or: pip install agentsec-agentwatch && agentwatch init
```

## Compatibility

See the generated [compatibility matrix](../../reference/compatibility.md) (regenerate with
`python scripts/generate_compatibility.py`; the generated block is deterministic and guarded by tests).
Claude Code is full-fidelity in v0.1.0; Cursor/Codex/Gemini/CrewAI/PydanticAI are **provisional (modeled)**
until real captures land (M14/N4).

## Security

See [security-audit.md](security-audit.md) (self-audit complete, 0 unresolved findings) and
[known-limitations.md](../../reference/known-limitations.md).

## Verification at this commit

- SDK/API/analytics: full suite green at ≥95% coverage; `ruff` zero; `mypy --strict` clean.
- Parity gate A1–A6: `python scripts/check_parity.py` — see [parity-checklist.md](parity-checklist.md).
- Fault-injection F1–F10, offline E2E, and soak jobs wired in CI.
- Security: [security-audit.md](security-audit.md) (0 unresolved findings) +
  [secret-scan-report.md](secret-scan-report.md) (gitleaks + trufflehog + pip-audit; `make security-scan`).
- Supply chain: [release-evidence.md](release-evidence.md) — `make release-dry-run` builds and verifies the
  bundle (CycloneDX SBOM + checksums + `verify-release`); CI signs and attests on the tag.
- Compliance: [compliance-matrix.md](compliance-matrix.md); OpenSSF:
  [open-source-checklist.md](../../reference/open-source-checklist.md).
- Versioning: one version across SDK/CLI/CHANGELOG, enforced by `tests/test_release_tooling.py`.
- First run: [first-run-evidence.md](first-run-evidence.md).

## Release actions (executed at M24 Release Readiness — not before)

The release tag is **cut at release readiness**, not during M13. See
[WBS M24](../../wbs/v0.1.0/wbs-v0.1.0-part8-field-test-release.md#milestone-m24--release-readiness)
(24.8/24.9).

- [x] At **M24**: cut and push the `v0.1.0` git tag (triggers `release.yml`: build + SBOM + checksums +
      Sigstore provenance + GitHub release).
- [x] At **M24**: make the `agent-exec-trace` predecessor repository **private** (retained, never deleted).
- [ ] At **M24**: record the OpenSSF Scorecard grade for the tag.
