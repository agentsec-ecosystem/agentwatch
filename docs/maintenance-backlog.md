# Maintenance Backlog

**BLUF:** Post-release docs/community/security work that is not on the v0.1.0 critical path.

Status: living.

- [ ] Publish the OpenAPI document for the read API. → **owned by v0.2.0 [PRD 46](prd/46-platform-sdk-and-growth.md) API-1**
- [ ] Split the JSON-schema contract into a versioned `schema/v1/` with a deprecation policy.
- [ ] Add Codemod for `agent_exec_trace` → `agentwatch` import migration. → **owned by v0.2.0
      [PRD 46](prd/46-platform-sdk-and-growth.md) GOV-1**
- [ ] Extend detector catalog documentation with thresholds + false-positive risks (from the shipped project). →
      **owned by v0.2.0 [PRD 43](prd/43-detector-credibility-and-evaluation.md) DET-3** (published effectiveness
      supersedes: per-detector precision/recall + thresholds + FP risks, CI-guarded)
- [ ] Add Tempo/Grafana example dashboards. → partially covered by v0.2.0
      [PRD 46](prd/46-platform-sdk-and-growth.md) EXA-1 (recipes); dedicated dashboards remain open
- [ ] Backfill accessibility automated checks into CI. (shipped in v0.1.0 M14 Q11 — verify and close)
- [ ] Add SBOM publishing to the release workflow. (shipped in v0.1.0 Q13 — verify and close)
- [ ] Reformat `services/analytics/src/analytics/scenario_validation.py` (v0.1.0 M23 FT-15) to satisfy `E501`;
      currently covered by a documented per-file waiver in `services/analytics/pyproject.toml` recorded at the
      M25 review (25.R) to keep the milestone diff scoped. No behaviour change.
