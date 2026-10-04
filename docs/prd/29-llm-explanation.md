# PRD 29 — LLM Explanation Layer

**BLUF:** A local-first narrative layer over already-redacted records — `agentwatch explain` and
`diff --explain`. The LLM explains what the deterministic pipeline found; it never decides what is
redacted or whether the chain is intact.

**Status:** proposed (2026-10-02) · **Parent:** agentsec-ecosystem #209

> Cross-cutting rules (PRD 19–29): fail closed and never silent (PRD 17); redaction before
> storage (DD-06); **the trust boundary stays deterministic — no LLM in redaction, validation, or
> chain verification** (this PRD, PRD 14/18); monitor-only, every hook exits 0 (R2); local-first,
> no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision
> (NFR-5); conformance and quality gates apply (NFR-11).

## Where the LLM fits — four roles, one hard line

agentwatch observes an LLM, so "where does the LLM fit?" must be answered precisely. Three roles
are legitimate; one is forbidden:

| Role | Meaning in agentwatch | Status |
|---|---|---|
| **The thing we observe** | The agent *is* an LLM; we record its actions and footprint (tool calls, tokens, model, prompts-as-reason-steps under privacy modes). We are not a prompt/completion analytics tool (PRD 14). | In scope |
| **The analyzer** | The M6 detector engine includes LLM-augmented detectors that classify anomalies with explanations. **Signals, never enforcement** (PRD 14/18: no ML in the enforcement path). | Parity |
| **The investigation assistant** | This PRD: narrate, explain, and diff sessions in English. | Proposed |
| **The security boundary** | Forbidden. No injection/intent classification as a boundary; enforcement is agentpolicy's. | Never |

**The hard line:** *the trust boundary is deterministic; the explanation layer is probabilistic.*
Redaction, hashing, and chain verification stay regex/sha256 — the "0 leaks" guarantee is only
provable because it is deterministic. An LLM may summarize what the deterministic pipeline found;
it must never decide what gets redacted or whether the chain is intact.

### M1. LLM investigation assistant — `agentwatch explain` · M7 (stretch to v0.1.x) · #211

**Why (evidence).** The operator's real question is rarely "what records exist?" but "what
happened here, in English?" A timeline answers the first; an LLM answers the second — narrative
summaries, diff explanations, incident drafts. This is the highest-leverage use of an LLM in the
product, and it stays entirely on the explanation side of the line.

**Behavior.** `agentwatch explain <session-id>` (and `--explain` on `diff`) generates a narrative
from already-redacted, already-stored records. The deterministic summary (tools used, counts,
outcomes, duration, cost) is **always printed regardless**; the LLM adds prose, not facts, and
cites the records it summarizes so output stays auditable.

**Data & schema impact.** A new `agentwatch/explain.py` that formats a deterministic summary and
optionally calls a configured model. No store-schema change; explain output is never written as a
record (it is derived, not evidence).

**Security & privacy.** **Local-first only**: a local model (Ollama/MLX) or an explicitly
configured endpoint; never silent egress (C7); the model call is disabled by default and requires
config. The model never touches raw transcripts or the redaction/validation/chain paths — it only
sees records that already passed DD-06. Output is labeled AI-generated with cited record ids.
Explain refuses to run against a broken chain without saying so (it does not "explain away" a
gap).

**Edge cases.** No model configured → deterministic summary only (no error). Model returns
unparseable output → fall back to the deterministic summary and say so. Very long sessions →
chunk/summarize with citations, never drop a chunk silently. A session with gaps/tombstones →
explicitly narrated as gaps, never smoothed over. Model hallucination → mitigated by always
printing the deterministic facts and requiring citations; users can ignore the prose.

**Dependencies.** Store/replay (M4/M5); privacy layer (M4); B1 health (surface model config
state); J3 cookbook (uses `explain` as the last step).

**Testing.** Explain output cites every claim's record; **no egress occurs without explicit
config** (a test asserts the network is untouched by default); the deterministic summary is
identical with the LLM disabled; a broken chain produces a refusal, not a narrative; a
hallucinated sentence cannot alter the deterministic section.

**Risks & mitigations.** Egress leakage (off by default, local-first, D-O). Hallucination
(deterministic facts always shown + citations). Scope creep into analytics (this is explanation
of stored records, not a prompt/completion tool). Model dependency (kept optional; a decision
must permit any new runtime dependency — NFR-5).

**Decision.** D-O (local model or explicit endpoint only; never silent egress; deterministic
summary always printed).

