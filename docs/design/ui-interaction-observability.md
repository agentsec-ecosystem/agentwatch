# Design — UI Interaction Observability

**BLUF:** The operator UI is itself instrumented (lightweight) so we can tell "nobody used the Anomaly
Inbox" from "it was broken". Local-only; no egress.

Status: **draft** (v0.3.0+; not v0.1.0).

## Signals (local-only)

- View opens / time-in-view.
- Filter usage (which filters are actually used).
- Replay actions (replay started, scrolled-to-anomaly).
- Errors (UI render/JS errors).

## Privacy

Local-only; never exported by default; aggregated, not per-user; follows the same privacy baseline as
records. No silent telemetry (DD-10).
