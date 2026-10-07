# Design — Managed-Policy Install

**BLUF:** How agentwatch installs and stays effective in Claude Code environments governed by managed settings, where
user/project hooks are blocked (`allowManagedHooksOnly`, `strictPluginOnlyCustomization`) and configuration arrives via
MDM or server-managed settings. Also defines what `doctor` may claim: never "installed" when policy blocks the recorder.

**Status:** implemented (2026-10-06, v0.2.0 M29) · **Milestone:** M29 · Sources:
[PRD 50](../prd/50-deployability-and-recorder-attestation.md), [claude-code-hook-contract.md](claude-code-hook-contract.md),
[recorder-attestation.md](recorder-attestation.md).

> **Implementation (M29 DEP-1, #441).** `agentwatch.managed_policy` reads the effective managed settings and
> `doctor` reports `hooks effective: yes | blocked by managed policy | unknown` (never "installed" when blocked).
> `init` warns when a user/project install would be inert and points at the managed path; `managed_install_artifacts`
> generates the inert managed hook / org-plugin / MDM artifacts. Detection only — never circumvention. **Verified
> on fixture configurations on macOS/Linux; the Windows managed-settings path and an on-a-clean-machine MDM
> verification are BLOCKED on WIN-1 (Windows service + named-pipe transport re-pointed to M31).** ADR-0028.

## The failure mode

`agentwatch init` writes into project `settings.local.json` / user `settings.json` (hook contract). Under
`allowManagedHooksOnly`, only **managed hooks** and hooks from **managed force-enabled plugins** run; user/project/local
hooks are blocked. In the environments the compliance PRDs target, a normal install is therefore **silently inert** — a
declared-in-principle but silent gap.

## Supported install modes

| Mode | Mechanism | Notes |
|---|---|---|
| user/project | hooks in `settings.local.json` / `settings.json` | current; byte-identical restore |
| endpoint-managed | hook entry in the org's `managed-settings.json` (MDM: Jamf/Iru, Intune, GPO) | requires admin; consent-first |
| org plugin | agentwatch as a plugin from an org marketplace, force-enabled in managed `enabledPlugins` | hooks run under `allowManagedHooksOnly` |
| server-managed | managed-settings delivered by the claude.ai admin console | same as endpoint-managed; approval dialog applies |

## `doctor` contract

`doctor` reports, per harness: `hooks effective: yes | blocked by managed policy | unknown`, plus the reason. It must not
report "installed" when the effective policy blocks the recorder. Detection is by reading the effective settings
precedence (managed > user > project) and the relevant booleans — no circumvention.

## Restore / uninstall

User/project installs restore byte-identically. Managed/plugin installs are removed by the admin mechanism; `uninstall`
reports that it has nothing to remove rather than editing managed files.

## Testing

- On a fixture "managed-only" config, `doctor` reports the true state and `init` explains the path (FT-DEP-1).
- Org-plugin fixture: hooks run under `allowManagedHooksOnly`; a non-force-enabled plugin hook is blocked.
- Restore test for user/project remains byte-identical.

## Decision

ADR-0028 — managed-policy install posture and the honest `doctor` claim. *(Verify against a real managed configuration
before GA; the exact key behaviour varies by Claude Code version.)*
