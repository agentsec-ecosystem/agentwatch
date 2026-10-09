# v0.2.0 — M32 (Release Readiness) Code Review Log

Record of the M32 release-readiness review and risk sign-off (issue #388). One row per finding; closed when
fixed + verified. Open items carry a reason and an owner.

**Scope reviewed:** M32 work items 32.1–32.27 (#396, #411, #412, #413, #398, #414, #399, #415, #397, #402, #416,
#417, #401, #418, #400, #404, #405, #406, #407, #423, #437, #492) and 32.T/32.D/32.R, plus the v0.2.0 field-test
evidence and the release artifacts.

## Findings

| # | Item | Finding | Severity | Resolution | Status |
|---|---|---|---|---|---|
| 1 | 32.8 | `make lint` / `make typecheck` returned only the **last** package's status (`for … done` with no `|| exit`), silently masking failures | High | Loops now fail on any package; this surfaced **51 `mypy --strict` errors + 3 ruff errors** in M30 files (`cli/main.py` + ~14 tests), all fixed; gates now green | Fixed |
| 2 | 32.4 | `security-scan` was red — gitleaks flagged synthetic `sk-abcdefgh1234` fixtures + an ephemeral console token in committed field-test evidence | Medium | allowlisted by path (fixtures + `field-test/**`); scan output dir moved v0.1.0 → v0.2.0; `make security-scan` now clean | Fixed |
| 3 | 32.4/32.5 | the scan script wrote v0.1.0 evidence for a v0.2.0 release | Low | default output → `docs/release/v0.2.0/security-scan/`; audit + secret-scan report published | Fixed |
| 4 | 32.16 | **ADR-0026 naming: the target name is TBD.** The install-confusion guard ships (NAM-1), but the **full rename** cannot execute without the name | High | Blocked on a decision — recorded on #404; not fabricated | **Open (needs name)** |
| 5 | CI | `detector-eval` workflow is red: it runs `scripts/detector_eval.py`, which reads a **gitignored** corpus (`services/analytics/data/detector-corpus-v0.json`) that `scripts/generate_detector_corpus.py` generates; the workflow never generates it | Medium | Carried — fix = add a generate step (or commit the corpus) | **Open** |
| 6 | CI | `Security Scan` (`security.yml`) reports a GitHub workflow-file issue on the branch | Low | Carried to the release commit | **Open** |
| 7 | 32.9/32.15 | Windows unsupported (FT-WIN-1 N/A) → the 3-OS timing gate (9) and the Scorecard grade (graded on `main`) are partial/not-claimable from the branch | Info (declared) | Stated in the release checklist + compliance matrix; not hidden | Accepted |

## Gate results (at HEAD, `feat-v0.2.0`)

| Gate | Result |
|---|---|
| `make test` | SDK **2473 passed** (95.26%), API **53 passed** (95.75%), analytics **742 passed** (96.28%), repo guard **47 passed** |
| `make lint` | clean (3 packages) |
| `make typecheck` | clean (3 packages) |
| `make security-scan` | clean (gitleaks 0; pip-audit 0 vulns; egress clean; 5 intentional trufflehog fixtures) |
| `make release-dry-run` | ok (build + CycloneDX SBOM + checksums + `verify-release`) |
| Field test | **92 PASS · 0 FAIL · 1 declared · 1 N/A** (90/92 grounded) |

## Risk sign-off (M32)

Reviewed the release evidence and docs across the milestone; the release-gate checklist (PRD 40 §5 gates 1–16)
is published with one **declared** partial (gate 9, Windows). No unresolved **code** findings. The open items
are: the **ADR-0026 name decision** (#4, blocks the rename in #404) and **two pre-existing CI workflows** (#5
`detector-eval`, #6 `security.yml`) that must be green **on the release commit** before merge/tag/publish
(32.20–32.22). Release actions (merge → main, tag, publish) are **not** executed by this review.
