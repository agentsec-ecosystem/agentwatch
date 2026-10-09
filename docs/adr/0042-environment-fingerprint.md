# ADR-0042 — Environment fingerprint contents

- **Status:** accepted (2026-10-07, v0.2.0 M30 ENV-1)
- **Context:** After a regression the first question is "what changed?", and the
  causes are mostly environmental — the model, the harness, the permission mode,
  the loaded capabilities, the rules files, the MCP surface, the effective
  recorder config. None of it was recorded per session, so `diff`/`drift` could
  only compare behavior, leaving the environment invisible.
- **Decision:**
  1. Each session derives a **content-free environment fingerprint** from what
     the record already holds: `model`, `harness`, `permission_mode`,
     `capabilities` (digest of the capability-snapshot set), `rules` (digest of
     the rules-file entries), `mcp_surface` (digest of the surveyed server
     surfaces) and `config` (the recorder-attestation config digest). Each absent
     component is the literal `unknown` — never inferred or defaulted to a value.
  2. The fingerprint is versioned and content-free: a `env1:<sha256>` digest over
     the components. It carries names, versions and digests only — no content.
  3. The delta is reported in a fixed priority order with `model` first, because
     a model change is the seed of most regressions. `diff` prints the environment
     delta above the behavior delta; `sessions --group-by-env` groups by the
     fingerprint; `drift` annotates a shift with environment changes in the same
     window using the wording **"coincides with"**, never "caused by".
- **Consequences:** "What changed?" is answerable from the record without a
  causal claim. Components that were never recorded stay `unknown` (an honest
  gap: a missing fingerprint component is not evidence that nothing changed).
- **Alternatives rejected:** fingerprinting only the model/harness (misses
  capability and config drift); defaulting absent components to a sentinel value
  (fabricates equality); presenting an environment change near a drift signal as
  its cause (a verdict this tool never makes).
