# ADR-0028 — Managed-policy install posture + honest `doctor`

- **Status:** accepted (2026-10-06, M29 DEP-1)
- **Decision:** agentwatch **detects** Claude Code managed policy
  (`allowManagedHooksOnly`, `strictPluginOnlyCustomization`) and states the truth
  per harness in `doctor`: `hooks effective: yes | blocked by managed policy |
  unknown`. It **never** reports "installed" when the policy blocks the recorder
  and **never circumvents** the policy (whether to allow the managed install is
  the org's decision). It ships an inert managed-install path (managed hook /
  force-enabled org plugin / MDM payload) that an admin applies.
- **Consequences:** a user/project install under a blocking policy is reported
  as inert, not silently successful; `init` warns and points at the managed
  path; user/project uninstall stays byte-identical-restoring; managed installs
  report that they are removed by the admin mechanism, not by `uninstall`.
- **Context:** under these controls user/project/local hooks do not run, so a
  normal install is silently inert exactly where regulated buyers deploy. The
  exact managed key behaviour varies by Claude Code version; the detection is
  version-tagged and must be re-verified against a real managed configuration
  before GA. The Windows managed-settings path and an on-a-clean-machine MDM
  verification are blocked on WIN-1 (re-pointed to M31).
- **Evidence:** `agentwatch.managed_policy`; `doctor`; `tests/test_managed_policy.py`.