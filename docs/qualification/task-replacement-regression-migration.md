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

## October 15 Core-backed migration map

Production remains at the accepted e581cfd5 implementation. These changes replace
test arrangements and removed internal expectations; they add no execution owner.

| Old arrangement | Retained behavior and replacement evidence |
| --- | --- |
| AgentTaskRegistry in artifact aggregation | Actual Core assignment lineage; depth/cycle protection, descendant transforms/artifacts and sibling isolation in test_artifacts_s5.py. |
| Removed child-rollup helpers | Actual Core parent-turn references and production artifact proposals; explicit publication preserves original evidence, and previews remain omitted. |
| Registry/inbox context-reference fixtures | Core task results, actual TurnRunner ownership, canonical Core mail and queued_user_input rendering; typed references, authorization and content/hash bounds remain asserted. |
| Relay sibling checkout and copied-model pin tests | Relay execution is excluded by the reviewed plan. Retained provenance serialization has exact identity/hash/metadata assertions without a Relay installation or skip. |
| JSON Question ledger and pre-publication session callback | The sole QuestionCommands owner confirms Core transitions before publication. New cases cover failed writes, answer/expiry arbitration and no implicit deadline. Session UI metadata is a projection rather than lifecycle authority. |
| Generated waited_tasks metadata and registry-based display-row fabrication | This removed internal field is not rebuilt. Canonical wait presentation is covered by test_canonical_wait_presentation.py, test_task_wait_presentation.py and test_wait_disclosure_contracts.py. Public wait_agent_tasks delegation/collection is covered by test_task_output_compatibility.py. The generic observer metadata extension and isolation are tested independently in test_tool_telemetry.py. |

These are construction/regression proofs, not live model qualification. The
selected cases were executed individually and sequentially with one worker;
receipts record actual execution and disposable-root custody. Removing a legacy
arrangement does not mark an acceptance-ledger row passed.

The first transform-metadata run exceeded its 120-second test limit during
apparent teardown. Its isolated daemon/console helper were identified and retired,
and its owned directory was removed. An unchanged diagnostic rerun passed with
normal cleanup. The initial failure remains recorded and its cause is unproven;
no production patch or timeout increase was made.

The composer busy-reference case initially failed its five-second admission
assertion. An unchanged rerun, with admission-state diagnostics added to that
assertion, passed. Its cause also remains unproven; no timeout or production
policy was changed. Both initial failures remain evidence, rather than being
erased by their subsequent passes.

## Transcript and MCP input migration

- Transcript acceptance now requires HTTP 202 and an assignment handle, then
  verifies that the original human notification and content reference occur in
  the confirmed Core recipient-input record. The deleted native journal and its
  projection metadata are not reconstructed. Existing strict transcript goldens
  still need reviewed updates for the changed acceptance surface.
- Ordinary async Questions no longer pause a model turn. The retained
  input-required transcript check uses a real plan approval, asserts original
  tool content and presentation, and repeats the public approval boundary to
  prove it does not publish a second Question or output. The separate common
  Question tests retain asynchronous posting, answer collection and Stop rules.
- The retained atom-writing regression instruments the confirmed recorder's
  actual append seam, preserving the assertion that a sealed part is not
  rewritten and only the remaining part plus envelope are appended.
- External MCP input now reaches the application's Question owner; a configured
  test client's automatic callback is deliberately replaced by that production
  handler. The public test answers the actual Questions. Exhausting an input
  driver after dispatch returns an uncertain handle with retry_safe=false and
  one attention notice, rather than a falsely clean rejection. Direct executor
  tests retain typed round-limit errors and malformed-wire protections.

These public checks and all three strict golden comparisons now pass. The
captured trace changes were inspected and mechanically restricted to removal
of duplicate user publication/retired input metadata, absent client ID handling
and generated identity renumbering. The earlier MCP test timeout is retained
in R74; its process family and runtime root are settled and removed. Nineteen
other test files still require migration, and no full-suite or CI pass is claimed.
