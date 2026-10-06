# Reference — Accessibility Conformance (v0.1.0)

**BLUF:** The operator UI targets **WCAG 2.2 Level AA**. That level is stated here, per view, with the
automated evidence that backs it, and CI fails if a view regresses. This is a **VPAT-lite** (an internal
conformance statement), not a certified third-party VPAT.

Status: **conforms (automated checks + manual baseline)** · Owner: operator UI (M7, M12, M14 Q11) ·
Issue: [#228](https://github.com/agentsec-ecosystem/agentwatch/issues/228)

## Conformance target

- **Standard:** Web Content Accessibility Guidelines (WCAG) **2.2**
- **Level:** **AA**
- **Scope:** the operator UI views (React, `apps/web`). The CLI and docs are out of scope for WCAG.

## Conformance by view (VPAT-lite)

Each cell is the WCAG 2.2 principle (Perceivable / Operable / Understandable / Robust). "Supports" means the
automated checks below pass and a manual keyboard/contrast review found no unmet criterion at AA.

| View | Perceivable | Operable | Understandable | Robust | Notes |
|---|---|---|---|---|---|
| Dashboard | Supports | Supports | Supports | Supports | axe (unit + Playwright incl. contrast); keyboard nav |
| Fleet Health | Supports | Supports | Supports | Supports | table semantics; axe (unit + Playwright) |
| Run Timeline | Supports | Supports | Supports | Supports | ordered spans; axe (unit + Playwright) |
| Agent Detail (span panel) | Supports | Supports | Supports | Supports | opened by keyboard (Enter); axe (unit) |
| Version Compare | Supports | Supports | Supports | Supports | labelled inputs; axe (unit + Playwright) |
| Anomaly Inbox | Supports | Supports | Supports | Supports | severity is text + icon, not color alone |
| Operator console (v0.2.0) | Supports | Supports | Supports | Supports | identity/attribution + SIEM health + detector markers; outcomes are text, not color alone; axe (unit) + keyboard journey (Playwright) |

## Automated evidence

| Check | Where | Covers |
|---|---|---|
| axe-core, each view rendered with fixtures | `apps/web/src/__tests__/a11y.test.tsx` | structure, names, roles, labels (all rules except contrast) |
| axe-core in a real browser, all routes | `apps/web/tests/e2e/a11y.spec.ts` | **color contrast** (jsdom cannot compute it) + full rules |
| Keyboard-only journey (CUJ-8 operator UI) | `apps/web/tests/e2e/a11y.spec.ts` | tab order, visible focus, Enter activation, no mouse |
| CI wiring | `.github/workflows/web.yml`, `.github/workflows/e2e.yml` | axe unit suite runs on every PR; Playwright runs on the stack |

The unit suite's own seeded-violation test proves the axe harness fails on a real violation; the e2e
contrast run measured and drove the fixes in this release.

## Known limitations (stated, not hidden)

- **Not a certified VPAT.** This is an internal statement; a third-party audit is post-traction.
- **Screen readers** were exercised manually (VoiceOver + NVDA spot checks), not by an automated
  screen-reader CI job; axe covers names/roles but not full reading order.
- **Reduced motion:** entrance animations are present; they honor `prefers-reduced-motion` and are frozen
  for the automated contrast measurement.

## Reproduce

```sh
# unit axe suite (no services)
cd apps/web && npm ci && npm test

# browser axe (contrast) + keyboard-only journey (needs the seeded stack)
make e2e
```
