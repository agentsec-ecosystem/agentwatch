# PRD 08 — Risks

**BLUF:** The hard parts are harness surface area and the standards play, not the recording itself.

| Risk | Impact | Mitigation |
|---|---|---|
| Cursor/Codex expose too little surface for full-fidelity recording | Harness coverage | Document gaps honestly; proxy-interposition where needed (open question) |
| OTel GenAI semconv still Development-grade | Format churn | Track upstream; version the schema; contribute rather than fork |
| Schema stewardship: alone vs OTel working group | Distribution vs control | Decide in v0.1.0; lean to propose upstream for adoption |
| Privacy/secret leakage in records | Trust | Redaction-by-default + attack-pack verification (R7) |
| Single-maintainer project fragility | Adoption/trust | Ecosystem governance: recruit a second maintainer (P0) |
| "Observability tool" sameness | Differentiation | The security-event schema is the differentiator; lead with it |
