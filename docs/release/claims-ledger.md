# Claims Ledger — v0.1.0

**BLUF:** Every public claim agentwatch makes is traced to **live evidence**. `scripts/check_claims.py`
fails when a claim has no evidence link, when a link is broken (a renamed test, a deleted file), or when
this table drifts from the ledger. A claim we cannot prove is removed, not softened.

Status: **enforced** (M14 Q9) · Ledger: [`claims-ledger.json`](claims-ledger.json) ·
Check: `python scripts/check_claims.py` (CI: `.github/workflows/claims.yml`)

## Claims

<!-- BEGIN GENERATED: claims -->
| ID | Claim | Source | Evidence | Last verified |
|---|---|---|---|---|
| `C1` | Every tool call is recorded redacted by default. | `README.md#what-it-does` | `test:packages/python-sdk/tests/test_redact.py::test_metadata_only_returns_none`<br>`test:packages/python-sdk/tests/test_secrets.py::test_api_key_masked_to_redacted_kind` | 2026-10-03 |
| `C2` | The redaction attack pack leaves zero secrets in the store. | `docs/release/v0.1.0/security-audit.md` | `test:packages/python-sdk/tests/test_secrets.py::test_private_key_block_masks_the_key_material`<br>`file:docs/release/v0.1.0/security-audit.md` | 2026-10-03 |
| `C3` | Local-first: no egress-capable runtime imports by default. | `README.md#what-it-does` | `test:packages/python-sdk/tests/test_egress_audit.py::test_sdk_source_is_egress_clean`<br>`script:scripts/dependency_egress_audit.py` | 2026-10-03 |
| `C4` | The local store is hash-chained and tamper-evident. | `README.md#what-it-does` | `test:packages/python-sdk/tests/test_store_vectors.py::test_store_verify_matches_the_verdict_table`<br>`test:packages/python-sdk/tests/test_store_hardening.py::test_manual_checkpoint_and_tamper_detection`<br>`file:schema/vectors/store/expected-verdicts.json` | 2026-10-03 |
| `C5` | OTLP export is gated on a redaction self-test. | `docs/release/v0.1.0/release-notes.md` | `test:packages/python-sdk/tests/test_selftest.py::test_self_test_blocks_export_when_pipeline_leaks`<br>`test:packages/python-sdk/tests/test_fault_injection.py::test_f6_self_test_failure_blocks_export` | 2026-10-03 |
| `C6` | A fresh machine reaches its first recorded tool call in 15 minutes or less with zero agent-side code changes. | `docs/release/v0.1.0/first-run-evidence.md` | `script:scripts/first_run_timing.py`<br>`file:docs/release/v0.1.0/first-run-evidence.md` | 2026-10-03 |
| `C7` | Session replay reconstructs a session's action timeline. | `README.md#what-it-does` | `test:packages/python-sdk/tests/test_replay.py::test_replay_orders_by_time_then_chain`<br>`test:packages/python-sdk/tests/test_replay.py::test_replay_matches_the_stored_records` | 2026-10-03 |
| `C8` | Replay-as-code exports a session with its chain segment for CI. | `docs/release/v0.1.0/release-notes.md` | `test:packages/python-sdk/tests/test_session_export.py::test_export_selects_one_session_with_chain_segment`<br>`test:packages/python-sdk/tests/test_session_export.py::test_ndjson_round_trips_through_reference_consumer` | 2026-10-03 |
| `C9` | Fault injection F1-F10 fail closed. | `docs/release/v0.1.0/security-audit.md` | `test:packages/python-sdk/tests/test_fault_injection.py::test_f3_store_full_fails_closed`<br>`test:packages/python-sdk/tests/test_fault_injection.py::test_f4_corrupt_chain_is_stopped_and_repairable` | 2026-10-03 |
| `C10` | Every CLI failure carries a machine-readable error code. | `docs/reference/errors.md` | `test:packages/python-sdk/tests/test_error_contract.py::test_every_subcommand_failure_emits_an_envelope` | 2026-10-03 |
| `C11` | The operator UI targets WCAG 2.2 Level AA, with axe coverage for every view and a keyboard-only journey. | `docs/reference/accessibility.md` | `file:docs/reference/accessibility.md`<br>`file:apps/web/src/__tests__/a11y.test.tsx`<br>`file:apps/web/tests/e2e/a11y.spec.ts` | 2026-10-03 |
| `C12` | Times are stored and compared in UTC; local rendering carries an explicit UTC offset. | `docs/reference/time.md` | `file:docs/reference/time.md`<br>`test:packages/python-sdk/tests/test_time_properties.py::test_relative_since_is_an_exact_utc_duration`<br>`test:packages/python-sdk/tests/test_time_properties.py::test_records_persist_and_reload_as_utc` | 2026-10-03 |
| `C13` | Releases ship with a CycloneDX SBOM, keyless Sigstore signatures, and SLSA L3 provenance, verifiable with agentwatch verify-release. | `docs/reference/release-integrity.md` | `file:docs/reference/release-integrity.md`<br>`file:.github/workflows/release.yml`<br>`test:packages/python-sdk/tests/test_release_pipeline.py::test_release_workflow_builds_signs_and_verifies` | 2026-10-03 |
| `C14` | Every rule-based detector fires on at least one field-test scenario (no silent detectors); the published precision/recall is generated and drift-guarded. | `docs/reference/detector-catalog.md` | `file:docs/reference/detector-catalog.md`<br>`test:services/analytics/tests/test_detector_non_silent.py::test_rule_detectors_are_non_silent`<br>`test:services/analytics/tests/test_detector_catalog.py::test_catalog_detector_metrics_are_generated_and_current` | 2026-10-05 |
| `C15` | Detector evaluation runs on a versioned, machine-checkable public corpus that is shape-synthesized and free of real secrets or PII. | `docs/design/detector-evaluation.md` | `file:schema/vectors/detectors/detector-corpus-v1.json`<br>`test:services/analytics/tests/test_detector_corpus.py::test_corpus_cases_are_machine_checkable`<br>`test:services/analytics/tests/test_detector_corpus.py::test_corpus_is_governance_clean` | 2026-10-05 |
| `C16` | The MCP interposition proxy speaks the 2026-07-28 Streamable HTTP transport statelessly: Mcp-Session-Id is neither required, forwarded, nor emitted, and MCP-Protocol-Version is relayed unchanged. | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_streamable_http.py::test_streamable_transport_strips_session_id_both_directions`<br>`test:packages/python-sdk/tests/test_mcp_streamable_http.py::test_streamable_transport_relays_protocol_version` | 2026-10-06 |
| `C17` | The MCP proxy records resources/read and resource links in tool results; the resource URI is metadata searchable with search --mcp-resource. | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_proxy_resources.py::test_resources_read_request_is_recorded`<br>`test:packages/python-sdk/tests/test_mcp_proxy_resources.py::test_recorder_frames_resource_links_in_a_tool_result`<br>`test:packages/python-sdk/tests/test_mcp_proxy_resources.py::test_search_filters_by_mcp_resource` | 2026-10-06 |
| `C18` | The MCP proxy records prompts/get and keeps the prompt name as metadata. | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_proxy_prompts.py::test_prompts_get_request_is_recorded`<br>`test:packages/python-sdk/tests/test_mcp_proxy_prompts.py::test_recorder_pairs_a_prompts_get_response` | 2026-10-06 |
| `C19` | The MCP proxy records elicitation and links the answer to approval provenance, with honest unknown when no action is exposed. | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_proxy_elicitation.py::test_accept_links_approval_to_user`<br>`test:packages/python-sdk/tests/test_mcp_proxy_elicitation.py::test_absent_action_is_honest_unknown`<br>`test:packages/python-sdk/tests/test_mcp_proxy_elicitation.py::test_recorder_pairs_a_server_elicitation` | 2026-10-06 |
| `C20` | The MCP proxy records the tasks/* lifecycle with the task id as metadata; Roots/Sampling/Logging are closed-by-spec (SEP-2577). | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_proxy_tasks.py::test_tasks_get_request_is_recorded`<br>`test:packages/python-sdk/tests/test_mcp_proxy_tasks.py::test_task_augmented_tool_result_keeps_the_task_id`<br>`test:packages/python-sdk/tests/test_mcp_proxy_tasks.py::test_recorder_pairs_a_tasks_request` | 2026-10-06 |
| `C21` | The MCP proxy declares a protocol-revision conformance matrix; its tested range tracks the newest revision and the compatibility table carries a Protocol column. | `docs/design/mcp-surface.md` | `test:packages/python-sdk/tests/test_mcp_protocol_matrix.py::test_tested_range_tracks_the_latest_revision`<br>`test:packages/python-sdk/tests/test_mcp_protocol_matrix.py::test_each_revision_has_a_replayable_fixture_pack`<br>`test:packages/python-sdk/tests/test_mcp_protocol_matrix.py::test_compat_table_gained_a_protocol_column` | 2026-10-06 |
| `C22` | The Gemini CLI adapter maps active_approval_mode to approval provenance and user.email to a hashed principal. | `docs/design/harness-adapter-design.md` | `test:packages/python-sdk/tests/test_gemini_attribute_mapping.py::test_active_approval_mode_auto_maps_to_auto`<br>`test:packages/python-sdk/tests/test_gemini_attribute_mapping.py::test_user_email_becomes_a_hashed_principal` | 2026-10-06 |
<!-- END GENERATED: claims -->

## Evidence syntax

| Reference | Must resolve to |
|---|---|
| `test:<path>::<function>` | A pytest test that still exists (checked by parsing the file's AST). |
| `file:<path>` | A committed file. |
| `script:<path>` | A committed script. |
| `workflow:<path>` | A committed CI workflow. |
| `doc:<path>` | A committed doc. |

## Rules

- A claim with **no evidence** fails the check — add evidence or remove the claim.
- A **renamed test** or **deleted file** breaks the link and fails the check.
- `last_verified` is an ISO date and may not be in the future.
- Regenerate the table with `python scripts/check_claims.py --write`; prove the check catches broken
  claims with `python scripts/check_claims.py --self-test`.
