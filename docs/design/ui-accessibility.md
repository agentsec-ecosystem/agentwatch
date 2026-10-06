# Design — Operator UI Accessibility

**BLUF:** The operator views (Fleet Health, Run Timeline, Version Compare, Anomaly Inbox, Agent Detail, and the
v0.2.0 **Operator** console — identity/attribution, SIEM health, detector telemetry) must be usable by keyboard
and screen-reader users, with sufficient contrast.

Status: **implemented** (v0.1.0 M7 + M12 pass; Operator console M27 UI-2/A11Y-1).

## Baseline

- Full keyboard navigation; visible focus.
- WCAG AA color contrast; never color-only status (pair with icon/text).
- Semantic headings and labels; anomaly severity conveyed in text.
- Replay/timeline readable as an ordered list.

## Verification

Automated axe checks run in the UI test suite
(`apps/web/src/__tests__/a11y.test.tsx`): each operator view renders with fixture
data and the suite fails on any violation. jsdom has no layout engine, so the
`color-contrast` rule is disabled there; a Playwright axe run in a real browser
(`apps/web/tests/e2e/a11y.spec.ts`, with contrast enabled) plus a keyboard-only
journey cover that gap, and a seeded-violation test proves the unit harness fails
on a real violation.

The stated conformance level and the per-view evidence live in the
[accessibility conformance reference](../reference/accessibility.md) (WCAG 2.2
AA, VPAT-lite). Manual keyboard pass and review against the baseline above
complement the automated checks.
