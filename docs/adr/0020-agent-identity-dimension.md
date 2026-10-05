# ADR-0020 — Agent identity dimension

- **Status:** proposed (2026-10-05, v0.2.0)
- **Context:** see [PRD 44](../prd/44-identity-enterprise-and-compliance.md) IDN-1..4 and
  [design/agent-identity.md](../design/agent-identity.md). NIST/CAISI/NCCoE and IETF AIMS/WIMSE name agent identity
  the top governance gap; AAT requires the fields.
- **Decision:** Add an `agent_identity` dimension (name/version/harness/model/workload-identity ref/credential
  class) plus a delegation chain where the harness exposes it; hash principals by default in `metadata-only`;
  identity fields never contain secret material; absent facts are `unknown`, never inferred.
- **Consequences:** Attribution completeness (CUJ-14/16) and AAT population; new privacy surface managed by hashed
  defaults + consent; requires a published AIMS/WIMSE/NCCoE mapping.
