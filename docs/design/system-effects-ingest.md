# Design — System-effects ingest (Linux, opt-in)

**BLUF:** `impact` stops at the tool-call layer. This design ingests the
**system-effects layer below it** — AgentSight/Tracee-shaped process-exec and
network-connect events — joined to sessions by **process lineage and time-window**,
so a spawned child process's network contacts become blast-radius facts.

Status: implemented (M29 SYS-1, #366). **Linux, opt-in; a declared gap on
macOS/Windows.**

## Why

A legitimate process making legitimate calls looks fine to EDR. AgentSight (SOSP
PACMI '25) showed the system-effects layer — syscalls, process lineage, network
beyond the model provider — is capturable and correlates upward. agentwatch answers
"did the spawned child process contact anything else?" by **reading** a foreign
system-event stream, never by probing.

## Non-negotiable posture

- **We do not build probes.** Linux-root eBPF violates our portability/trust
  posture (PRD 45 §SYS-1). This is a reader for a stream a host already produced.
- **Linux, opt-in.** :data:`agentwatch.system_ingest.SUPPORTED_PLATFORMS` is
  `{"linux"}`. `agentwatch ingest --format system-ingest` refuses without
  `--consent`; the library refuses without `opted_in=True`.
- **Declared gap elsewhere.** macOS/Windows are **not covered**
  (`platform_covered("darwin") is False`); the gap is published, not hidden.
- **Monitor-only.** Ingest changes nothing about what the observed processes do.
- **No egress.** Local file/stdin only.

## Labeling and no-silent-trust

Every ingested record carries:

- `harness == "system-ingest"` and a `producer` of
  `kind=ingest` / `name=system-ingest` (the M15 S26 provenance distinction), and
- `environment.source == "system-ingest"` plus `pid`, `ppid`, `join`
  (`lineage` | `unowned` | `outside-window`) and `joined`.

The lower layer is never silently trusted: a record whose process lineage is not
owned by **exactly one** known session is filed under `unjoined:system-ingest`
and is never folded into a session's blast radius. An explicit `session_id`
inside the foreign event is recorded as `foreign_session_hint` for triage but is
**not** used to attribute (it is the lower layer telling us the answer).

## Join algorithm

1. Build a parent map (`pid → ppid`) from the events.
2. Walk each event's ancestry to the nearest pid owned by a session.
3. Join only when exactly one session owns the lineage **and** the event time is
   within the session window (record `started_at`…`ended_at`, ±300 s slack).
4. Otherwise `unjoined`. Ambiguous pids (two sessions) and out-of-window events
   never join — precision over recall.

## Published false-join precision

Measured over the committed, shape-synthesized corpus
`packages/python-sdk/tests/fixtures/system-ingest/lineage-corpus.json` with known
session membership (no real capture content):

| Corpus | Precision | Recall | False joins |
|---|---|---|---|
| `system-ingest-lineage-corpus/1` | **1.00** | **1.00** | 0 |

`agentwatch.system_ingest.PUBLISHED_PRECISION` is the machine-readable form and
`tests/test_system_ingest.py::test_published_false_join_precision_matches_the_corpus`
holds it to the corpus. This is a synthetic-tree measurement, not a field claim.

## Blast radius

Network-connect records carry the destination on `tool.server` (structural truth,
present even in metadata-only mode); `agentwatch.classify` maps the `system:`
tool namespace to a `network:destination` fact, so `impact` and `blame` extend to
syscall truth without changing the record schema.

## Operations

```
agentwatch ingest events.jsonl --format system-ingest --consent
```

| Property | Value |
|---|---|
| Coverage | Linux only (declared gap: macOS/Windows) |
| Opt-in | required (`--consent` / `opted_in=True`) |
| Egress | none (local file/stdin) |
| Record schema | unchanged; labeled `source: system-ingest` |
| Probes | none (we do not build eBPF) |

## References

- PRD 45 §SYS-1 (`docs/prd/45-new-capture-surfaces.md`)
- `docs/design/harness-adapter-design.md` (capture levels)
- `docs/reference/known-limitations.md` (declared gap)
