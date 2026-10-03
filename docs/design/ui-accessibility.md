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

Manual keyboard pass and review against the baseline above. Automated a11y checks
(e.g. axe) are **not yet wired into the UI test suite** — tracked by #63.
