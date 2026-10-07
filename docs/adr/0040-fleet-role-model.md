# ADR-0040 — Fleet role x data-class read-access model

- **Status:** accepted (2026-10-06, v0.2.0 M29 ACC-1)
- **Context:** Recording individuals' agent activity triggers employee-monitoring and
  access-control obligations. IDN-1 hashes on-behalf-of principals and S21 records data
  movement, but a multi-user/fleet view defined no *roles* — nothing said who may see whose
  sessions, at what fidelity, or that a denial happened at all.
- **Decision:**
  1. The read model is a documented, enforceable **role x data-class** matrix: roles
     `self` / `team-reviewer` / `security-auditor` / `admin` against data classes
     `metadata` / `identity-hashed` / `identity-resolved` / `content` / `evidence`
     (`agentwatch.access`). The `self` role has **no cross-user grant**.
  2. A cross-user read the role is not granted returns **nothing** and is itself appended
     as a metadata-only `store-access` record (S21), so the subject can see who read their
     records and when (`agentwatch access log --owner <id>`).
  3. `identity-resolved` is **never** reachable by a plain read. Resolving a hashed
     principal to a person is a separate, explicit, recorded action by a permitted role
     (`security-auditor` / `admin`).
  4. The default fleet profile is **least-privileged**: `privacy.mode=metadata-only`
     stores no content and identity is hashed (`DEFAULT_FLEET_PROFILE`).
- **Consequences:** Role *assignment* (which human is which role, and under a managed
  policy) is owned by 29.DEP-1 (PRD 50, WS-B). This decision defines the model and the
  enforcement/recording boundary it must adopt, not a second policy engine. The matrix is
  published (`agentwatch access matrix`) and tested; content visibility is gated on the
  store actually holding content, so a metadata-only fleet cannot leak arguments.
- **Alternatives rejected:** per-view ad-hoc filtering (unprovable, drifts); a single
  `admin` gate with no team scope (breaks least privilege); auto-resolving hashed
  principals (turns a correlation handle into a surveillance identifier).
