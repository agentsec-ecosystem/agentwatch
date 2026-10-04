# PRD 34 — Content-Flow Forensics

**BLUF:** Record two deterministic **data-flow facts** that matter after an incident: where an untrusted
content came from before it was used as an instruction (S22), and where an exposed secret went afterward
(S23). Both are observation-only, local, and keyed so the store holds no recovered content.

**Status:** shipped (2026-10-03) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M18

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06);
> the trust boundary stays deterministic — **no LLM in redaction, validation, or chain verification**
> (PRD 14/18); monitor-only, every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6); no
> new runtime dependency without a recorded decision (NFR-5); conformance and quality gates apply (NFR-11).

Both items are the closest proposals in the set to the PRD 14 line ("no injection classification as a
boundary"), so this PRD states the guardrail up front: **the records state a flow fact and stop.** They never
say "injection," never score, never block. Recording a deterministic provenance edge is not classifying
intent — and each item gets its own decision record because of how close it reads.

### S22. Untrusted content → argument flow capture · v0.1.0 · (new)

**Why.** The dominant real-world agent compromise is a **data flow**: content arrives from somewhere untrusted
(a fetched page, a file, an MCP tool response, an issue body) and later reappears as an *instruction* — a shell
argument, a URL, a file path. PRD 14 forbids injection classification as a security boundary, and that has been
read as "stay away from injection entirely." But the flow itself is a deterministic, recordable fact: content X
entered at record 12 and a substring of X left as an argument at record 19. Recording it needs no model, no
heuristic, and no verdict, and it is the single most-requested agent-forensics capability nothing provides.

**Behavior.** With `tool.response` captured (I1), fingerprint response content in shards (rolling hash over
normalized n-grams); when a later tool *argument* matches a stored shard, record a `content-flow` observation:
source record id, sink record id, matched length, source class (`web | file | mcp | tool-output`).
`agentwatch flow <session-id>` renders the graph.

**Data & schema impact.** New observation carried on the record (reuses the metadata-only event convention);
fingerprints are keyed HMACs so the store holds no recovered content.

**Security & privacy.** Deterministic, local, observation-only. Keyed HMAC (per-install key) keeps content
unrecoverable even if the store leaks. No egress.

**Edge cases.** Large responses → cap response size and sample. A shard matching many sinks → capped fan-out
with counts. An empty/whitespace match → ignored. A source record that was redacted → flow recorded over what
remains stored, labelled as such.

**Dependencies.** I1 tool responses (shipped), M4 secrets (HMAC keying), S3 (argument extraction).

**Testing.** A fixture where a fetched page's text reappears in a later shell argument produces one
`content-flow` edge; a non-matching argument produces none; no raw content appears in the stored record.

**Risks & mitigations.** Read as injection detection by users or marketing → name it `content-flow`, never
"injection," and state the distinction in the docs; shard-matching cost → cap + sample.

**Decision.** New — explicit decision record that this is a flow fact, not classification (given how close it
reads to PRD 14's line).

### S23. Trace an exposed secret across the session · v0.1.0 · (new)

**Why.** `secret-detected` fires and the investigation stops — the operator learns a secret was *seen* and
nothing about where it *went*. The question that decides whether to rotate a credential is: after it appeared,
was it echoed into a later tool call, written to a file, sent to a network tool, or committed? The redactor
already recognizes every occurrence deterministically; it treats each sighting as independent instead of as
the same secret.

**Behavior.** Give each detected secret a stable keyed fingerprint (HMAC, never the value) so repeat sightings
link, and record the exposure path: first sighting → each subsequent record containing the same fingerprint →
whether any of those records was a network, write, or VCS tool (S3's classifier).
`agentwatch secrets [--session-id]` lists distinct credentials by kind with their path and a plain
`rotate: recommended | no evidence of egress` line.

**Data & schema impact.** Reuses the `secret-detected` event + the S22 fingerprint machinery; no schema change
beyond the observation.

**Security & privacy.** Deterministic, local, metadata only; recommends nothing operational beyond "consider
rotating." Keyed HMAC with a per-install key, documented in the threat model.

**Edge cases.** "No evidence of egress" is the honest phrasing — absence of a record is not proof of absence.
A secret seen once → path of length one. A secret in a redacted field → not traced (content not stored).

**Dependencies.** M4 secrets, S3 classifier, S22 (shared fingerprint machinery).

**Testing.** A secret detected then echoed into a network tool yields `rotate: recommended` with the path; a
secret seen once with no later sighting yields "no evidence of egress"; no value appears in output.

**Risks & mitigations.** Fingerprints enabling confirmation attacks if the store leaks → keyed HMAC with a
per-install key, documented in the threat model.

**Decision.** New — fingerprint keying and the exposed-path vocabulary; explicit decision record that the
output is evidence, not a rotation instruction.
