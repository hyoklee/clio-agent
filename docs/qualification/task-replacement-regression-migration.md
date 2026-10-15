# Remaining legacy regression migration

Initial production implementation is present; this checklist concerns regression construction and qualification. Snapshot: R42 plus the first three R43 migrations; AST-only inspection of 1,098 Python test/helper files, 46 candidate files and 288 retired-binding findings, with no parse errors. This is advisory evidence, not collection, behavioral execution or complete coverage proof. A candidate may require fixture migration, removal of engine-specific assertions, or preservation as a legitimate historical decoder test; never delete it automatically.

The native extension-registry expectations were additionally migrated by semantic inspection: the old custom Tasks entry is replaced by the actual SDK factory while Apps/input and catalog contracts remain covered. The queue-identity regression was added after the AST snapshot. Initial test construction remains unfinished.

| Candidate file | Required disposition | Status |
| --- | --- | --- |
| tests/test_gact/test_a2ui_actions.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_a2ui_actions_narration.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_a2ui_capabilities.py | Inspect the 8 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_a2ui_pack_composability.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_a2ui_v3.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_action_cards.py | Inspect the 2 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_artifacts_s4.py | Inspect the 8 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_artifacts_s5.py | Inspect the 12 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_artifacts_s7_export.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_artifacts_s7_grounding.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_artifact_response_presentation.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_composer_af1_fix_round.py | Inspect the 20 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_composer_fix_round.py | Inspect the 29 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_context_references.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_declared_workflows_s5.py | Inspect the 16 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_document_preview_semantics.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_gact_v3.py | Inspect the 6 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_hook_dispatcher.py | Inspect the 2 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_interactions.py | Inspect the 22 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_operator_playbooks.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_part_atom_minter.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_paused_transcript_persistence.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_plan_exit.py | Inspect the 9 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_plan_save_reuse.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_plan_variants.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_projection_fix_round.py | Inspect the 7 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_question_answers_1448.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_question_expiry_publication.py | Inspect the 11 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_session_export_semantics.py | Inspect the 2 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_skill_effects.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_source_connect_runtime.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_spotter_arming.py | Inspect the 11 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_spotter_availability.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_spotter_clearance.py | Inspect the 8 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_spotter_watcher.py | Inspect the 33 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_stall_replanning.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_tool_telemetry.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_turn_runner_s1.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_turn_transcript_equivalence.py | Inspect the 1 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_turn_transcript_pr3.py | Inspect the 2 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_variant_drafts.py | Inspect the 5 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_variant_pick_close.py | Inspect the 8 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_wire_semantics_p5.py | Inspect the 8 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_providers/test_claude_code_cancel.py | Inspect the 4 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_providers/test_claude_code_session_lifecycle.py | Inspect the 13 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |
| tests/test_gact/test_attention/reviewer_fixture.py | Inspect the 2 retired-binding findings; preserve independent behavior and map removed engine assertions to the R2 ledger | pending |

Completed construction in this packet:

- MCP v2 conformance: removed the deleted mutable task-store fixture and custom extension declaration; retained protocol, native SDK/CLI routing, guarded input and Apps cases.
- MCP capability composition: native SDK Tasks plus fresh CLIO Apps/input advertisements, including the known-extension catalog and actual SDK extension type.
- Reasoning inheritance: fixed parent-turn metadata replaces registry lookup in the test fixture; same-model, different-model, later-parent-turn and global-level checks remain. Explicit session deletion now calls the existing reasoning cleanup owner, with a public-route regression retaining another session's records.
- Blueprint lazy mounting: removed two tests of the deliberately deleted relay federation-epoch lifecycle. Independent namespace, workspace and lease cases remain; general lease safety stays required under A07/Q8.
- Queue identity: different idempotency keys cannot accept one client message identity; existing transcript ownership and an intervening public acceptance during preflight are checked before mutation.

All cases are constructed, not passed. Migration acceptance, scoped behavior execution, F03, exact-head CI and Q1–Q9/R1–R6 remain required. Current reviews finished on R42; the composer identity collision is the demonstrated source blocker being corrected. Generic corruption availability and unmeasured timestamp/performance concerns did not authorize another task policy.
