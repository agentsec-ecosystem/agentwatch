# Design — Content-Flow Forensics

**BLUF:** `content-flow` edges and secret exposure paths are **deterministic data-flow facts**, not
injection or intent classification. agentwatch records *that* content moved from a source record to a
later argument and *where* a seen secret went; it never says "injection", never scores, and never blocks.
This is the explicit boundary the PRD 14 rule ("no injection classification as a boundary") requires.

**Status:** published (v0.1.0) · **Milestone:** M18 · Sources: [PRD 34](../prd/34-content-flow-forensics.md),
[PRD 14](../prd/14-non-goals.md), [threat model](threat-model.md).

## The PRD 14 line

PRD 14 forbids treating injection classification as a security boundary. Recording a provenance edge is
not classifying intent: "the bytes `ignore all previous instructions` entered at record 12 and a
substring of them left as a shell argument at record 19" is arithmetic over already-stored records.
It is a *fact an investigator can use*, not a verdict the recorder renders.

The user-facing name is `content-flow` — never "injection". Docs, CLI help, and output all use it.

## How it works

1. When a tool **response** is captured (I1), its text is normalized and split into word-n-gram shards
   (5 words, ≥20 chars, capped per response).
2. Each shard is hashed with a **per-install keyed HMAC-SHA256** (16-hex prefix).
3. When a later tool **argument** matches a stored shard fingerprint, a `content-flow` edge is recorded:
   source index, sink index, source class (`web | file | mcp | tool-output`), matched length, and the
   fingerprint — never the content.
4. `agentwatch flow <id>` renders the graph; `--record` appends metadata-only observations.

Edge cases: large responses are capped and sampled; a shard matching many sinks is capped with a match
count; empty/whitespace shards are ignored; a redacted source is matched over what remains stored.

## Secret exposure path (S23)

The redactor recognizes every secret occurrence deterministically but treats each as independent. M18
gives each detected secret a stable **keyed fingerprint** (never the value) attached to its
`secret-detected` evidence, so repeat sightings link. The exposure path is first sighting → each later
record with the same fingerprint → whether any sink was a network/write/VCS action (the M17 classifier).

`agentwatch secrets` prints one plain line per distinct credential:

```
api-key 1f2e3d4c5b6a  sightings=2 rotate: recommended
  path: #0 Bash -> #1 Bash
  sinks: network:destination
```

- **Evidence, not an instruction.** The output is a plain recommendation to consider rotating; agentwatch
  takes no operational action (no blocking, no credential store access).
- **"No evidence of egress"** is deliberate: absence of a record is not proof of absence.

## Keying and the store

Fingerprints use a per-install key at `<store>/flow.key` (created `0600`, owner-only) or
`AGENTWATCH_HMAC_KEY`. The store holds only keyed digests, so even a leaked store does not reveal the
matched content, and an attacker without the key cannot confirm a guessed plaintext offline. The daemon
ensures the key at start; the adapter only fingerprints when a keyed function is supplied.

See the [threat model](threat-model.md) for the confirmation-attack note.
