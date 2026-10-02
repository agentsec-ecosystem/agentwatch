# Build Risks — agentwatch v0.1.0

**BLUF:** Risks specific to *building* v0.1.0 (PRD 08 covers product risks). Each has a mitigation and a
trigger.

| # | Risk | Mitigation | Trigger |
|---|---|---|---|
| BR1 | Claude Code hook API shape changes mid-build | Pin to a documented version; abstract the event in the adapter; revisit at build start | Claude Code releases a hook change |
| BR2 | OTel GenAI semconv churns mid-build | Track upstream; version our schema; propose upstream early (DD-05) | Upstream breaking change to `execute_tool` |
| BR3 | Hash-chain fsync dominates the perf budget | Batch fsync (group commits); benchmark early in Part 4 | p99 > 5 ms in perf test |
| BR4 | Redaction regex perf or false negatives | Pre-compile regex; attack pack in CI; corpus grows | Attack pack finds a leak |
| BR5 | Parity work pulls scope into v0.1.0 | v0.1.0 is foundation only; parity lands v0.2.0–v1.0 (PRD 05/09) | A PR adds a detector or UI to v0.1.0 |
| BR6 | Single-maintainer bottleneck | Governance ladder; recruit a second maintainer (P0) | Any release gate blocked on one person |
| BR7 | Local socket perms / multi-user issues | Per-user socket path; document single-user v0.1.0 | Multi-user bug report |
