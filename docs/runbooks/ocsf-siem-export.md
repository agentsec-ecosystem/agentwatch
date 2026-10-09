# Runbook — OCSF / SIEM export

Goal: push agentwatch security events to a SOC as **OCSF 1.5.0**, events-only and
redaction-gated.

```sh
# One-off: export a session's events as OCSF 1.5.0 NDJSON
agentwatch export-session <session-id> --format ocsf > events.ocsf.ndjson

# Validate the stream with the reference consumer before you ingest it:
python examples/ocsf_consumer.py --input events.ocsf.ndjson

# Continuous forwarding: opt-in sinks in config (file / webhook / syslog).
#   [sinks]
#   enabled = true
#   targets = ["file:///var/log/agentwatch/events.ndjson", "syslog://siem.internal"]
# The S10 redaction self-test must pass, or the sink stays off.
```

## Verify

- [ ] `export-session --format ocsf` carries `metadata.version == "1.5.0"`.
- [ ] `examples/ocsf_consumer.py` reports `0 rejected`.
- [ ] The sink forwards **security events only** (never full records); a delivery failure shows `degraded`.
- [ ] Every event type maps to an OCSF class/category/activity (or an explicit `unmapped`).

## Notes

- agentwatch is **not** a SIEM (PRD 14): export is a pure transcode, no ingestion/network/state.
- Events-only and bounded; forwarding is not alerting (no rules/thresholds/routing in the sink).
- OCSF version is pinned; mapping drift fails CI.
