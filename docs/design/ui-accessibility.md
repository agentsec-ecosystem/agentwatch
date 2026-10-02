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

Automated a11y checks in the UI test suite (e.g. axe) plus manual keyboard pass in CI/manual release
checklist.
