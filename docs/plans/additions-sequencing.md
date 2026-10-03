# Additions — sequencing (PRD 19–30)

Feeds the WBS: where each addition lands relative to the existing milestones M5–M15.

| Milestone | Additions (PRD item) |
|---|---|
| **M5** | Lifecycle hooks + usage (A1–A5, PRD 19/20); `/healthz` (B1); event emit (B2); gap/quarantine (B3/B4); doctor (C1); tail (C2); async hooks (P1); M4 minors (E3); spool/dedup/export-cursor/format-version (F1–F4); verify-privacy (G1); consent init + preflight (G3/G4); CLI polish (H6); conformance runner (O1) |
| **M6** | Cost rollup (A5); detector starter pack (L1); tool responses (I1) feeding detectors |
| **M7** | Terminal `view` (H4); LLM assistant `explain` (M1, stretch) |
| **M8** | Import (H1); tail alerts (H5); investigation cookbook (J3); golden corpus (I2) |
| **M9** | MCP attribution + inventory (D1); prompt fingerprint (D2); project filter (I4); purge (I5); search (H3) |
| **M10** | MCP proxy (N1); OTel ingestion (N2); fake-harness emitters (N3); compatibility matrix (N4); publish contract (J1); resumed-session correlation (I3) |
| **M12** | Clock skew (B5); checkpoints (E1); repair (E2); perms/logs (F5/F6); continuous verify (G2); durability + offline proof (K1/K2); service units (K3) |
| **M13** | Session export (J2); evidence bundle; (J1 publish) |
| **Nightly** | Soak (K4); harness drift job (N4) |

Sizing: most A–D and F–I are small (≤ a day); healthz, event emit, cost capture, import, diff,
view, repair, MCP proxy, and ingestion are medium (1–5 days).

## Per-item issue map (all additions)

Every idea → PRD → milestone → GitHub issue.

| Milestone | Item | PRD | Issue |
|---|---|---|---|
| M5 | A1 | `docs/prd/19-agent-lifecycle.md` | #165 |
| M5 | A2 | `docs/prd/19-agent-lifecycle.md` | #166 |
| M5 | A3 | `docs/prd/19-agent-lifecycle.md` | #167 |
| M5 | A4 | `docs/prd/19-agent-lifecycle.md` | #168 |
| M5 | A5 | `docs/prd/20-usage-accounting.md` | #169 |
| M5 | B1 | `docs/prd/22-self-observability.md` | #170 |
| M5 | B2 | `docs/prd/23-event-interchange.md` | #171 |
| M5 | B3 | `docs/prd/21-data-integrity.md` | #172 |
| M5 | B4 | `docs/prd/21-data-integrity.md` | #173 |
| M5 | C1 | `docs/prd/22-self-observability.md` | #175 |
| M5 | C2 | `docs/prd/22-self-observability.md` | #176 |
| M5 | E3 | `docs/prd/21-data-integrity.md` | #181 |
| M5 | F1 | `docs/prd/21-data-integrity.md` | #182 |
| M5 | F2 | `docs/prd/21-data-integrity.md` | #183 |
| M5 | F3 | `docs/prd/21-data-integrity.md` | #184 |
| M5 | F4 | `docs/prd/21-data-integrity.md` | #185 |
| M5 | G1 | `docs/prd/24-operator-trust.md` | #188 |
| M5 | G3 | `docs/prd/24-operator-trust.md` | #190 |
| M5 | G4 | `docs/prd/24-operator-trust.md` | #191 |
| M5 | H6 | `docs/prd/26-investigation.md` | #197 |
| M5 | O1 | `docs/prd/27-harness-expansion.md` | #216 |
| M5 | P1 | `docs/prd/28-performance-operability.md` | #217 |
| M6 | I1 | `docs/prd/25-capture-fidelity.md` | #198 |
| M6 | L1 | `docs/prd/30-analytics-signals.md` | #210 |
| M7 | M1 | `docs/prd/29-llm-explanation.md` | #211 |
| M8 | H1 | `docs/prd/26-investigation.md` | #192 |
| M8 | H2 | `docs/prd/26-investigation.md` | #193 |
| M8 | H4 | `docs/prd/26-investigation.md` | #195 |
| M8 | H5 | `docs/prd/26-investigation.md` | #196 |
| M8 | I2 | `docs/prd/27-harness-expansion.md` | #199 |
| M9 | D1 | `docs/prd/25-capture-fidelity.md` | #177 |
| M9 | D2 | `docs/prd/25-capture-fidelity.md` | #178 |
| M9 | H3 | `docs/prd/26-investigation.md` | #194 |
| M9 | J3 | `docs/prd/26-investigation.md` | #205 |
| M10 | I3 | `docs/prd/25-capture-fidelity.md` | #200 |
| M10 | I4 | `docs/prd/25-capture-fidelity.md` | #201 |
| M10 | I5 | `docs/prd/26-investigation.md` | #202 |
| M10 | J1 | `docs/prd/23-event-interchange.md` | #203 |
| M10 | N1 | `docs/prd/27-harness-expansion.md` | #212 |
| M10 | N2 | `docs/prd/27-harness-expansion.md` | #213 |
| M10 | N3 | `docs/prd/27-harness-expansion.md` | #214 |
| M10 | N4 | `docs/prd/27-harness-expansion.md` | #215 |
| M13 | B5 | `docs/prd/21-data-integrity.md` | #174 |
| M13 | E1 | `docs/prd/21-data-integrity.md` | #179 |
| M13 | E2 | `docs/prd/21-data-integrity.md` | #180 |
| M13 | F5 | `docs/prd/28-performance-operability.md` | #186 |
| M13 | F6 | `docs/prd/28-performance-operability.md` | #187 |
| M13 | G2 | `docs/prd/22-self-observability.md` | #189 |
| M13 | J2 | `docs/prd/23-event-interchange.md` | #204 |
| M13 | K1 | `docs/prd/28-performance-operability.md` | #206 |
| M13 | K2 | `docs/prd/28-performance-operability.md` | #207 |
| M13 | K3 | `docs/prd/28-performance-operability.md` | #208 |
| M13 | K4 | `docs/prd/28-performance-operability.md` | #209 |

## PRDs 31–39 — new v0.1.0 additions (2026-10-03)

Source: `next-ideas.md` (39 features S1–S39, 6 CUJs, 13 quality raises Q1–Q13, 9 standards items W1–W9). All
are added to the **v0.1.0** PRD set as feature work: PRDs [31–39](../prd/README.md) and CUJ-8–14 in
[PRD 04](../prd/04-users-and-cujs.md). Issue numbers are TBD (not yet created).

Suggested landing (all within v0.1.0; from `next-ideas.md` §6, adjusted so nothing is deferred to v0.1.x):

| Milestone | Items |
|---|---|
| **M10** (in flight) | Q5, Q4, Q13, Q8 — CI and release plumbing before more features land |
| **M11** | S2, S3, S5, S6, S7 |
| **M12** | Q1, Q2, Q3, Q6, Q7, Q12, S4 |
| **M13** | S1 (with W6, Q9), S8, S9, S12, W1, W2, W5, W7, W8 |
| **M14–M15** | Remaining S/Q/W items (S10, S11, S13, S14–S39, Q10, Q11, W3, W4, W9) and CUJ-8–14 verification |

Per-item detail lives in the PRDs; each section carries its own Why / Behavior / Data & schema impact /
Security & privacy / Edge cases / Dependencies / Testing / Risks & mitigations / Decision.
