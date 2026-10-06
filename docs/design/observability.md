# Observability

**BLUF:** What agentwatch emits (its own signals) and what it records (agent signals), and the backends it
targets.

## Emitted signal

- **OTel GenAI spans** — `execute_tool` for tool calls; child spans for plan/retrieval/memory/approval.
- **Security events** — `denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`, `drift-detected`.
- **Trace context** — W3C `trace_id`/`span_id` for cross-harness correlation.
- **Fleet rollups** (M11 R13) — opt-in, self-hosted aggregation of a host's local store into a
  self-hosted aggregate, grouped by host/agent/version (`agentwatch fleet`). No egress.
- **Drift signals** (M11) — a `drift-detected` event when a stored metric deviates from its **trailing
  baseline** (rolling mean/stdev, never a fixed threshold), optionally correlated with deployment markers
  (`agentwatch drift`). Signals are observations only — no enforcement; the CLI exits `0`.

## Attributes

Mapping of agentwatch fields to OTel attributes: [design/otel-mapping.md](otel-mapping.md).

## v0.2.0 additions

- **Streaming** (PRD 42 STR): the daemon pushes record notifications to API/UI over a local socket/WebSocket;
  live timeline + anomaly inbox; the store stays **append-then-verify** and views reconcile to it
  ([streaming-views.md](streaming-views.md)). p99 hook→view ≤ 1 s.
- **SIEM/OCSF sinks** (PRD 44 SIEM): the security-event stream is exported as conformance-tested **OCSF 1.5.0**
  with a CI-exercised reference consumer (`examples/ocsf_consumer.py`, M27 SIEM-1) plus a **Syslog** sink
  (`examples/security_event_consumer.py` is the event flavor); events-only, bounded, redaction-gated (S10),
  `degraded` visible on backpressure.
- **Detector telemetry** (PRD 43 DET-5): opt-in, local-only, content-free fired/suppressed/false-positive markers
  (`agentwatch.detector_telemetry`, off by default, bounded NDJSON), feedable to SIEM consumers.
- **v0.2.0-expanded** (PRD 49–59): authorization/oversight provenance
  ([authorization-provenance-v2](authorization-provenance-v2.md)), recorder attestation
  ([recorder-attestation](recorder-attestation.md)), harness-native telemetry join
  ([native-telemetry-join](native-telemetry-join.md)), capability supply chain
  ([capability-supply-chain](capability-supply-chain.md)), code provenance ([code-provenance](code-provenance.md)),
  local console + embedded index ([local-console](local-console.md)), agent interfaces
  ([agent-interfaces](agent-interfaces.md)).

### The SOC/SIEM context (why the sinks are shaped this way)

The SOC is being rebuilt around agents, which defines what a telemetry *source* must provide:

- **Microsoft ISOC in Defender** (Sept 2026) folded Sentinel into Defender — agent-first SOC, 500+ connectors,
  agents given "the same signals, context, and controls as human analysts." Analysts flagged the gap: "Microsoft
  has not published details on how agent actions within ISOC are logged, audited or reversed" — the hole we fill.
- **Exabeam Agent Behavior Analytics** extends UEBA to agents — baselining agent activity; it needs identity on
  every event (IDN-1) and behavioral telemetry as data.
- **Menlo MARS → Google Security Operations** (Sept 2026): runtime agent detections stream into a SOC where
  playbooks correlate and analysts approve response — detections must arrive as **structured, streamable events**.
- **Trend Agentic SIEM / Rapid7 Incident Command**: vendors repositioning SIEM around "automation, identity
  telemetry, and data context."
- **Context research (Feb 2026)**: European SIEM revenue +4% but mid-market (501–1000 seats) **+288%**; MDR +18.9%
  — small teams without 24/7 SOCs buy unified platforms for compliance reassurance.
- **Ingestion economics**: Microsoft made first-party telemetry free; third-party ingest is expensive → lean,
  high-signal, structured events (our six event types + OCSF) are more adoptable than raw firehoses. Operators keep
  the chain locally and forward events only.

**SOC-buyer checklist** our sinks must satisfy: (1) structured schema-stable events; (2) streaming push with
bounded queues + visible health; (3) identity attribution on every event incl. delegation; (4) behavioral
baselines available as data (bd1 fingerprints + detector telemetry); (5) forensic export an analyst can hand over
(evidence bundles + AAT); (6) retention control (chain local, events forwarded; AAT §9 windows). Position: the
**agent telemetry source** for the SOC stack — not a SIEM (PRD 14).

## Backends

Phoenix · Jaeger/Tempo · Splunk · Datadog · any OTLP endpoint. Export is opt-in and gated on the redaction
self-test (DD-09).

## Agentwatch about itself (meta)

Recording health is visible — "couldn't read the run" is distinguished from "clean run" (the AgentObservatory
lesson). Agentwatch surfaces its own status rather than failing silently (NFR-12).
