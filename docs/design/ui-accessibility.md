# Design — Operator UI Accessibility

**BLUF:** The operator views (Fleet Health, Run Timeline, Version Compare, Anomaly Inbox, Agent Detail) must
be usable by keyboard and screen-reader users, with sufficient contrast.

Status: **draft**.

## Baseline

- Full keyboard navigation; visible focus.
- WCAG AA color contrast; never color-only status (pair with icon/text).
- Semantic headings and labels; anomaly severity conveyed in text.
- Replay/timeline readable as an ordered list.

## Verification

Automated axe checks run in the UI test suite
(`apps/web/src/__tests__/a11y.test.tsx`): each operator view renders with fixture
data and the suite fails on any violation. jsdom has no layout engine, so the
`color-contrast` rule is disabled there and contrast remains a manual/Playwright
check; a seeded-violation test proves the harness fails on a real violation.

Manual keyboard pass and review against the baseline above complement the
automated checks.
