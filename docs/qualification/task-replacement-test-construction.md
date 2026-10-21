# Task replacement test construction

This is the completed initial construction-phase coverage map. Statements such
as "written; not executed in this phase" below describe that historical phase,
not the current execution status. The complete clio-agent `e700f15f` CI baseline
failed; its coordinated correction coverage is constructed. See the [current status](task-replacement-current-status.md)
and [live execution sheet](task-replacement-live-experiments.md); later bugs and
their added regression cases do not reopen the initial implementation milestone.

Core production reference: 00b3092dc6a31fe1f76fe80a5c87ffe462a4ba33.
GACT production reference: 0a4ca5d5915a0add61cd5048b742161092468481.
GACT test-only commit: 0795157b5652efb8a497950cdc92344eec5bbca3.
The production implementation is unchanged during this construction phase.

The human required the entire regression test set to be written before any more
tests, CI, live checks or bug fixes. No pytest collection/execution, native service,
model or browser qualification was launched in this phase. AST parsing and
filesystem inventory read code without importing product/test modules.
Test source formatting, scoped Ruff and Mypy (seven new/shared modules), and
GACT TypeScript (2 GiB) pass. They do not execute the tests or qualify runtime
behavior. Missing-module/symbol and syntax inventories are empty.

Written tests are not passing tests. This map preserves the R2 behavior
obligations while replacing removed registries, JSON intent stores, blocking asks
and direct turn-spawn arrangements. Independent workload algorithms remain
covered. New cases intentionally require the specified behavior even when the
current implementation may fail it.

| Ledger rows | Required regression area | Written cases | Status |
| --- | --- | --- | --- |
| F01, F03, F05 | Snapshot kinds, immutable identity, missing history, bounded indexed reads | [test_task_history.py](../../tests/test_arc/test_task_history.py), [test_task_boundary_contracts.py](../../tests/test_arc/test_task_boundary_contracts.py), [test_task_replacement_contracts.py](../../tests/test_arc/test_task_replacement_contracts.py) | Written; not executed in this phase |
| F02, M05 | Content-first recording, staging, fixed input commitment and collection races | [test_task_history.py](../../tests/test_arc/test_task_history.py), [test_approval_input_boundaries.py](../../tests/test_arc/test_approval_input_boundaries.py), [test_publication_recovery_contracts.py](../../tests/test_arc/test_publication_recovery_contracts.py) | Written; not executed in this phase |
| F04, M06 | Idempotent data-only legacy migration and unproven acknowledgements | [test_task_replacement_migration.py](../../tests/test_arc/test_task_replacement_migration.py), [test_composer_fix_round.py](../../tests/test_gact/test_composer_fix_round.py) | Written; not executed in this phase |
| F06, A02, A03 | Fixed context, successor ownership, restart and recovery | [test_conversation_owner_contracts.py](../../tests/test_arc/test_conversation_owner_contracts.py), [test_task_control_recovery.py](../../tests/test_arc/test_task_control_recovery.py), [test_retained_task_behaviors.py](../../tests/test_arc/test_retained_task_behaviors.py) | Written; not executed in this phase |
| N01, N02, N03, N04, N08, N17 | Native SDK adoption, transport contracts, raw validation and queue configuration | [test_native_task_client_contract.py](../../tests/test_tools/test_native_task_client_contract.py), [test_task_receipt.py](../../tests/test_tools/test_task_receipt.py), [test_external_task_observations.py](../../tests/test_arc/test_external_task_observations.py) | Written; not executed in this phase |
| N05, P02, P03 | Immutable input binding, partial answers, callback re-entry and Question arbitration | [test_external_input_identity_contracts.py](../../tests/test_arc/test_external_input_identity_contracts.py), [test_question_resolution_contracts.py](../../tests/test_arc/test_question_resolution_contracts.py), [test_approval_input_boundaries.py](../../tests/test_arc/test_approval_input_boundaries.py), [test_interactions.py](../../tests/test_gact/test_interactions.py), [test_question_expiry_publication.py](../../tests/test_gact/test_question_expiry_publication.py) | Written; not executed in this phase |
| N06, N07, N09, N10, N15 | Trusted worker admission, root isolation, physical cleanup and shutdown | [test_native_owner_contracts.py](../../tests/test_arc/test_native_owner_contracts.py), [test_native_cleanup_visibility.py](../../tests/test_arc/test_native_cleanup_visibility.py), [test_native_cancellation_dispatch.py](../../tests/test_gact/test_native_cancellation_dispatch.py), [test_replacement_turn_resources.py](../../tests/test_gact/test_replacement_turn_resources.py) | Written; not executed in this phase |
| N11, N13, N14 | Attention/final outcomes, recovery, provisional recording and known-owner control | [test_task_replacement_contracts.py](../../tests/test_arc/test_task_replacement_contracts.py), [test_task_boundary_contracts.py](../../tests/test_arc/test_task_boundary_contracts.py), [test_native_cancel_recovery.py](../../tests/test_arc/test_native_cancel_recovery.py), [test_task_retirement_contracts.py](../../tests/test_arc/test_task_retirement_contracts.py) | Written; not executed in this phase |
| N12, W01, W02, W03, W06 | Provider custody, downloads, indexing, atomic manifests and scoped access | [test_globus_download.py](../../tests/test_gact/test_globus_download.py), [test_source_transfer_async_lifecycle.py](../../tests/test_gact/test_source_transfer_async_lifecycle.py), [test_connected_storage_boundary.py](../../tests/test_gact/test_connected_storage_boundary.py), [test_source_connect_runtime.py](../../tests/test_gact/test_source_connect_runtime.py), [test_linked_storage.py](../../tests/test_gact/test_linked_storage.py) | Written; not executed in this phase |
| W04, N16 | Confined shell/output limits and retained inline MCP error handling | [test_shell_server.py](../../tests/test_tools/test_shell_server.py), [test_shell_output_spill.py](../../tests/test_tools/test_shell_output_spill.py), [test_mrtr.py](../../tests/test_tools/test_mrtr.py) | Written; not executed in this phase |
| W05 | Artifact ownership, digest/result references and descendant workspace grounding | [test_agent_task_artifacts.py](../../tests/test_gact/test_agent_task_artifacts.py), [test_artifacts_s7_export.py](../../tests/test_gact/test_artifacts_s7_export.py), [test_artifacts_s7_grounding.py](../../tests/test_gact/test_artifacts_s7_grounding.py), [test_turn_transcript_pr3.py](../../tests/test_gact/test_turn_transcript_pr3.py) | Written; not executed in this phase |
| A01, A04, A05, A06, A07 | One assignment engine, inference-only capacity, retirement and closed subtree admission | [test_conversation_owner_contracts.py](../../tests/test_arc/test_conversation_owner_contracts.py), [test_turn_runner_s1.py](../../tests/test_gact/test_turn_runner_s1.py), [test_async_tool_session.py](../../tests/test_gact/test_async_tool_session.py), [test_declared_workflows_s5.py](../../tests/test_gact/test_declared_workflows_s5.py), [test_retained_task_behaviors.py](../../tests/test_arc/test_retained_task_behaviors.py) | Written; not executed in this phase |
| A08 | Watcher, skill, producer, context and provenance behavior over common owners | [test_spotter_watcher.py](../../tests/test_gact/test_spotter_watcher.py), [test_spotter_clearance.py](../../tests/test_gact/test_spotter_clearance.py), [test_skill_effects.py](../../tests/test_gact/test_skill_effects.py), [test_projection_fix_round.py](../../tests/test_gact/test_projection_fix_round.py), [test_session_export_semantics.py](../../tests/test_gact/test_session_export_semantics.py) | Written; not executed in this phase |
| C01, C02, C03 | Authorized query, mixed controls, cursor and independent subscription delivery | [test_task_replacement_contracts.py](../../tests/test_arc/test_task_replacement_contracts.py), [test_task_query_boundaries.py](../../tests/test_arc/test_task_query_boundaries.py), [test_task_collection_authorization.py](../../tests/test_arc/test_task_collection_authorization.py), [test_cross_workflow_session_contracts.py](../../tests/test_arc/test_cross_workflow_session_contracts.py) | Written; not executed in this phase |
| M01, M02, M03, M04, M07 | Pending-only capacity, full history, feedback/goal gates, queue edits and admission | [test_task_history.py](../../tests/test_arc/test_task_history.py), [test_conversation_owner_contracts.py](../../tests/test_arc/test_conversation_owner_contracts.py), [test_composer_fix_round.py](../../tests/test_gact/test_composer_fix_round.py), [test_composer_af1_fix_round.py](../../tests/test_gact/test_composer_af1_fix_round.py), [test_turn_runner_s1.py](../../tests/test_gact/test_turn_runner_s1.py) | Written; not executed in this phase |
| P01 | Immediate Question handle, async choice and Stop independence | [test_async_yield_output.py](../../tests/test_gact/test_async_yield_output.py), [test_interactions.py](../../tests/test_gact/test_interactions.py), [test_question_answers_1448.py](../../tests/test_gact/test_question_answers_1448.py), [test_variant_drafts.py](../../tests/test_gact/test_variant_drafts.py), [test_variant_pick_close.py](../../tests/test_gact/test_variant_pick_close.py) | Written; not executed in this phase |
| K01, K02, K03, K04, K05, K06 | Shipped compatibility delegates, committed evidence and bounded output pages | [test_assignment_evidence_contracts.py](../../tests/test_arc/test_assignment_evidence_contracts.py), [test_task_output_compatibility.py](../../tests/test_arc/test_task_output_compatibility.py), [test_task_observation_compatibility.py](../../tests/test_arc/test_task_observation_compatibility.py) | Written; not executed in this phase |
| D01, Z01 | Canonical agent/tool guidance and removed-authority guards | [test_task_guidance.py](../../tests/test_gact/test_task_guidance.py), [test_task_tool_descriptions.py](../../tests/test_gact/test_task_tool_descriptions.py), [test_task_replacement_guard.py](../../tests/test_task_replacement_guard.py) | Written; not executed in this phase |
| U01 | Progressive disclosure, stopping/cancellation and mixed task controls | [shared-task-ui.test.tsx](../../external/gact-tui/web/src/components/clio/shared-task-ui.test.tsx), [task-activity-ui.test.tsx](../../external/gact-tui/web/src/components/clio/task-activity-ui.test.tsx), [task-wait-presentation.test.ts](../../external/gact-tui/web/src/components/clio/task-wait-presentation.test.ts) | Written; not executed in this phase |
| U02 | Explicit human grants, separate rights, revocation and errors | [session-access.test.tsx](../../external/gact-tui/web/src/components/clio/session-access.test.tsx) | Written; not executed in this phase |

## Reported defect and added coverage

The empty-wake defect has six root/child cases across pending Questions, Shell
work and descendants, plus negative controls retaining genuine failure behavior:
[assignment empty wakes](../../tests/test_arc/test_assignment_empty_wake_contracts.py).
No production fix or test pass is claimed.

Two actual declared workflow executions (with a test-only model body) exercise
separate identities, human grants, messages/replies, observation/subscriptions,
waits, denied control, revocation and independent owner/subscriber delivery.
This is an integration test definition, not actual-model Q5 qualification.

The new SessionAccess UI cases cover progressive disclosure, default rights,
read-only grants, explicit control/descendant choice, empty rights, revocation
and errors. They have not been executed or rendered against a real service.

## Execution gate

After construction, run the complete relevant regressions individually and
sequentially with one worker, retaining failures and skips as failures. Run
scoped formatting/lint/types/guards and required CI. Establish that regression
baseline before restarting actual-model live qualification. Fix discovered
production bugs explicitly; do not weaken or remove their required behavior.

The following ledger rows are acceptance/process gates, not substitutes for
written unit/integration tests: D02 (real website media), Z02 (executed checks/CI),
Z03 (frozen tuple), Z04 (physical cleanup), Z05 (publication go/no-go).
Q1–Q9 and final-candidate R1–R6 repetitions remain live gates. Existing live
harnesses and earlier evidence do not count as a passing replacement matrix.
