# PRD 50 — Deployability & Recorder Attestation

**BLUF:** Make the recorder installable and *provably on* in managed-policy enterprise environments, and publish the
real cost. Claude Code managed settings can block user/project hooks (`allowManagedHooksOnly`, `strictPluginOnlyCustomization`),
so a normal install is silently inert exactly where regulated buyers deploy; the recorder cannot prove after the fact
that it was running; and the end-to-end hook wall-clock a developer feels is unpublished.

**Status:** shipped in v0.2.0 (2026-10-08) — originally proposed v0.2.0-expanded (2026-10-05) · **Parent:** agentsec-ecosystem #209 · **Milestone:** M26–M28 ·
**Depends on:** PRD 28, PRD 32, PRD 46 (WIN-1, fleet) · **Extends:** `init`, `doctor`, recorder attack matrix, R2 · **Adds:** CUJ-25

> Cross-cutting rules (PRD 19–30): fail closed and never silent (PRD 17); redaction before storage (DD-06); the trust
> boundary stays deterministic — no LLM in redaction, validation, or chain verification; monitor-only, every hook exits
> 0 (R2); local-first, no egress without explicit opt-in (R6); no new runtime dependency without a recorded decision
> (NFR-5); conformance and quality gates apply (NFR-11).

Through-line: **"installed" must never be reported when policy blocks the recorder; "recording was on at 14:03" must
be a fact, not an assumption; and the developer must be able to see what it costs.**

## What it delivers, why, and for whom (CUJs)

| Feature | What (outcome) | Why (problem/market) | CUJ |
|---|---|---|---|
| DEP-1 | Managed-policy install path + honest `doctor` | Managed settings block user/project hooks; MDM is how enterprise rolls out Claude Code | 25 |
| DEP-2 | Session-start recorder attestation + `recorder-config-changed` | Stripping hooks leaves no chain record; hook/config files are an attacker persistence target | 25 |
| DEP-3 | Published end-to-end hook wall-clock per OS + budget + CI gate | The budget measures in-process cost; the user feels process-spawn cost per tool call | 1, 25 |

## DEP-1 — Install that survives managed-policy environments · (new)

**Why.** Claude Code's supported enterprise controls include `allowManagedHooksOnly` (only managed hooks and hooks
from managed force-enabled plugins run), `strictPluginOnlyCustomization`, and MDM deployment templates (Jamf/Intune/GPO).
agentwatch installs into project `settings.local.json`/user `settings.json` (`design/claude-code-hook-contract.md`), so
under these controls the recorder is off — a *silent* gap in the corpus. *(Verify against a real managed config before
GA.)*

**Behavior.** A supported install path for managed environments: agentwatch distributed as a managed hook / org-marketplace
plugin, with MDM-friendly artifacts; `init`/`doctor` detect a managed-policy environment and state plainly whether the
recorder can run.

**Acceptance.**
- [ ] `doctor` reports, per harness, "hooks effective: yes / blocked by managed policy / unknown" — never "installed"
      when policy blocks it (FT-DEP-1).
- [ ] A tested recipe exists for server-managed settings, endpoint-managed (MDM) settings, and org-marketplace plugin
      distribution; each verified on a clean machine.
- [ ] `uninstall` remains byte-identical-restoring for user/project installs, and a clear no-op for managed installs.
- [ ] The compatibility matrix gains a "managed-policy" column with honest tiers.

**Security & privacy.** Consent-first; detects policy, does not circumvent it (that is the org's decision).
**Dependencies.** WIN-1, fleet (R13), per-harness install research.
**Risks & mitigations.** Policy varies by version → version-tagged recipes + drift. **Decision.** ADR-0028.

## DEP-2 — Recorder attestation · (new)

**Why.** `design/recorder-attack-matrix.md` concedes stripping hooks is "detectable" only by `status/doctor` and "a
silent edit leaves no chain record." An auditor cannot later prove recording was active. CVE-2026-25725 (sandbox escape
via persistent hook injection in `settings.json`) shows hook/config files are an attacker target; harness
`ConfigChange` hooks do not fire for managed-policy changes.

**Behavior.** Each session begins with a chain-recorded **attestation fact**: which hook sources were effective, a
digest of the effective hook/permission config (no values), whether managed-only policy applied, and the permission
mode. Digest changes mid-session or between sessions raise `recorder-config-changed`.

**Acceptance.**
- [ ] `coverage` and `evidence` include the attestation; a session without one is `attestation:absent`, not "complete".
- [ ] Hooks stripped between two sessions → `recorder-config-changed` at next session start + a classified gap for the
      unattested interval (FT-DEP-2).
- [ ] Digest/booleans only; property test proves no config values/secrets.
- [ ] Compliance-report row "recording active during period" cites attestations.

**Security & privacy.** Digests and booleans only; same-user forgery is *not preventable* — document as detectable by
cross-checks with native telemetry (PRD 51), not guaranteed.
**Dependencies.** DEP-1, S5, S2, PRD 51.
**Risks & mitigations.** Over-claiming attestation integrity → public non-claim. **Decision.** ADR-0029.

## DEP-3 — Publish end-to-end hook cost · (new)

**Why.** `design/performance-budget.md` budgets "hook→socket ≤1 ms" and `reference/performance.md` publishes in-process
p99, but each hook is a fresh interpreter process, twice per tool call (`design/claude-code-hook-contract.md`). The
latency a developer feels is unpublished on any OS; Cursor/Windows costs differ; HTTP hooks exist as an alternative.

**Behavior.** A published, CI-gated end-to-end hook wall-clock (p50/p99) on macOS, Linux, Windows per shipped harness,
with a user-visible budget and a regression gate; the budget decision (and any transport change) recorded.

**Acceptance.**
- [ ] `reference/performance.md` gains an "end-to-end hook" table per OS, generated by the perf gate.
- [ ] Budget stated in user terms ("adds < X ms per tool call at p99") and enforced in CI (FT-DEP-3).
- [ ] A 500-call session overhead figure is quoted.
- [ ] A missed budget yields a tracked ADR, not a silent miss.

**Security & privacy.** Measurement only.
**Dependencies.** Perf gate (Q4), WIN-1.
**Risks & mitigations.** Noisy runners → drift band, as existing gates. **Decision.** ADR-0030.

## Not goals

Building an MDM product; preventing users from disabling recording; prescribing a transport before DEP-3 measures.

## Sources

Claude Code managed-settings / server-managed-settings / settings-reference docs (2026); CVE-2026-25725 (GitLab
Advisory DB, 2026-02-06); Anthropic containment/auto-mode engineering posts. Local analysis files 02 and 07.
