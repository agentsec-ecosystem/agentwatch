# WBS — agentwatch v0.1.0

**BLUF:** v0.1.0 delivers P0 requirements R1–R8 for Claude Code, monitor-only, local-first, with the
security-event schema defined and replay working.

## Parts

| Part | Scope | Requirements |
|---|---|---|
| 1 | Foundation — repo, CLI skeleton, config, CI | — |
| 2 | Record format + security-event schema | R1, R5 |
| 3 | Claude Code adapter (Pre/PostToolUse hooks) | R2, R3 |
| 4 | Local daemon + storage | R6 |
| 5 | Redaction-by-default | R7 |
| 6 | OTel GenAI export | R4 |
| 7 | Session replay | R8 |
| 8 | CLI + first-run (≤15 min) | R2, CUJ-1 |
| 9 | Field test + release readiness | all |

> Detailed work items to be enumerated during the v0.1.0 build (issue-per-item, milestone-tracked).
