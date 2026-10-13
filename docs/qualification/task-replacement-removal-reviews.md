# Independent removal reviews - first pass

Reviewed local core69b19afda93213b38a7b4d0c238d2b16ee25c00e against5475042feda49c1354f9f88b19051cb53d7fa740; GACT unchanged at32044a387472b1495f60a24c862c6b9e4292abc3. Both source reviews were read-only, not runtime acceptance. Both verdicts: removal incomplete; rebuilding remains gated.

Astra: existing Review task architecture plan chat, turn01a13681-cbca-7512-abaf-d34f42333bed. Claude Code2.1.296, configured model claude-sonnet-5-5, PID59888/birth1791915882.8518937,50 read-only tool calls,exit0, original authentication hash unchanged. No credentials copied. Owned review cache D:/Temp/clio-task-plan-review-5475042f-c1 awaits cleanup confirmation. No product qualification launched.

## Astra findings

**Removal is not complete; I would keep the rebuild gate closed.** I reviewed removal commit `69b19afd` against `5475042f`, including the retained callers. These findings concern surviving policy and deletion scope—not the expected broken imports.

1. **[P1] The old pending-steer authority survives.**
   [MessageIntentStore](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/message_intents.py:301) still implements claim, release, cancellation, consumption and pruning in `message_intents.json`. [Composer initialization](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/composer_runtime.py:37) still installs it, and message submission still writes pending steers. Remove this delivery lifecycle and its callers. Preserve future-message queue functionality and data-only legacy decoding separately.

2. **[P1] Question handling still contains the retired delivery variants.**
   [Question creation](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/session_questions.py:77) accepts `response_mode` and independently puts sessions into `waiting_user`. [Answer preparation](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/question_answer_message.py:137) still requires async answers to use the future-message queue, with corresponding queue settlement callers. Deleting the ledger imports leaves that policy intact. Remove the alternate agent-Question paths while preserving permission and external-input safeguards.

3. **[P1] Both provider bridges retain the explicitly rejected executor dependency.**
   [Codex direct](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/providers/codex/direct_engine.py:284) and [Claude sessions](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/providers/claude_code_sessions.py:560) still perform unbounded `queue.get` through the shared default executor. Neither file changed. Removing the whole-turn pools therefore leaves another capacity bottleneck identified by R2. Include these bridge sections in the removal inventory; preserve the underlying provider implementations.

4. **[P1] `StepRecorder.carry_over` was deleted beyond the task-removal scope.**
   The [expanded manifest](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:341) groups it with task input commitment, but its implementation restores missing conversation context from durable operations or saved transcript history. It does not depend on the retired task authority. Its [independent recovery test](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_gact/test_context_recovery.py:199) remains. Preserve this algorithm and explicitly retain its recovery scenarios in the ledger. The concern is lost behavior, not the dangling call.

5. **[P2] The preserved native configuration contract is incomplete.**
   [Defaults](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/config.defaults.yaml:388) retain URLs and concurrency, but omit the existing queue overrides and `CLIO_TASKS_{SHELL,STORAGE}_{URL,QUEUE,CONCURRENCY}` mappings from the preservation inventory. The deleted host distinguished stable persistent queues from incarnation-specific memory queues. Record those settings and identity semantics explicitly before rebuilding.

6. **[P2] The removal guard misses concrete surviving policies and some reintroductions.**
   [Its checks](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/scripts/check_task_replacement_removal.py:155) cover selected imports and references, but do not check removed module paths or class/function definitions. A restored `class AgentTaskRegistry` definition can evade the symbol check. Pending-steer lifecycle methods and old Question modes are also outside its coverage. Expand the guard from the corrected removal inventory; retain its honest statement that static checks cannot prove architectural completeness.

The main registry, journal, custom MCP drivers, child pools, composed idle hooks and special relay execution modules **were removed**. Shell and storage workload algorithms largely remain intact. Relay still has an old [capability projection binding](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/system.py:580) to clean up; unrelated infrastructure and provenance should remain.

No files changed, and no tests, guard, build or runtime processes were launched. The three protected human files remain untouched.

## Claude Code findings

# R2 removal review of `69b19afd` (read-only)

**Verdict: removal is not complete.** The core authorities named in the manifest are gone. I did not run the guard myself. It reports 0 violations, but it only checks its own denylist. The commit still leaves live task and Question state, wiring and policy, and it loses some non-task algorithms that the ledger doesn't track.

I used Git read-only on `69b19afd` and `5475042f`, plus greps and an AST scan of the tree. I ran no tests or builds and edited no files. I did not write the plan file Plan Mode suggested, because you asked for no edits.

Retained, as required: Shell confinement, process tree, output and spill code, the storage provider/transfer/index/manifest code, and the seven named independent test files. `config.defaults.yaml` keeps `agent_tasks.max_concurrent`, and the commit adds native concurrency 10 and `gact.mailbox.max_pending_messages`.

## P0 – delete before rebuild (leftover authority or policy)

1. **A mutable task store is still wired into `SessionStore`.**
   - `gact/sessions.py:275,287,452` still holds `self.task_store`, calls `install_session_task_store(self)` and `task_store.on_session_deleted`.
   - `gact/routes/system.py:441` still calls `task_record_store_is_durable`.
   - `gact/routes/interactions.py:530` still lists `app_task_store(app)`.
   - These are all mutable-store residue the guard can't see.
2. **The Question mirror is still live.**
   - `app.state.user_questions` is still created at `gact/app.py:1177`. It is read by about 12 retained modules, including a2ui delivery, `variant_close`, `composer_runtime:175`, `routes/interactions`, `session_questions` and `question_answer_message`.
   - `app.py:2161-62` still calls the deleted `restore_user_questions` and `restore_pending_ask_user_questions`.
   - `gact/interaction_types.py:29,94` keep the `response_mode: "blocking"|"async"` variant.
   - `gact/question_answer_message.py:137-197` keeps async-answer queueing.
   - `interaction_types.py:127` keeps the `"mcp_task_input"` kind.
   - `elicitation_forwarding.py:37` keeps `forward_child_question_to_parent`, a parent mirror of child Questions with `FORWARDED_QUESTION_SOURCE`. `resolve_cancelled_question` there still calls the deleted `relay_forwarded_cancel`.
   - Delete the async variant, the forwarded mirror and the dict. Rebuild the permission and external-input safeguards over the one Core record.
3. **The loop-inbox and idle admission policy survives in the retained engine.**
   - `gact/agents/clio_react.py:480` still reads `state.pending_loop_inbox_drain` in `_arrivals`.
   - `clio_react.py:374` still calls `carry_over` and `:422` still calls `commit_input`, both of which were deleted.
   - `gact/turn_start_offloop.py:170` still calls `accept_session_run` and `:227` still calls `stage_session_inputs`.
   - `gact/turn.py:454` still calls `refresh_session_inputs`, and `:681,701` still call `require_execution_allowed` and `retained_model_metadata`.
   - `gact/composer_runtime.py:169` and `gact/turn_state.py:291` also still call deleted functions.
   - Some of these are ordinary missing bindings. Anything that encodes admission or consumption order, such as `stage_session_inputs`, `refresh_session_inputs`, `accept_session_run` and the `pending_loop_inbox_drain` read, should be removed rather than left dangling.
4. **Dead shutdown-cutoff and settlement scaffolding remains in `gact/turn_runner.py`.**
   - `DRAIN_REASON_SERVER_SHUTDOWN` (line 59), `_MAX_DRAIN_PASSES` (line 70) and `DrainOutcome` (line 93) are left behind.
   - The docstring, lines 1-35, still describes `drain` and the per-depth children pool.
   - `set_segment_settler`, `_settlers` and `_settle_and_release` (lines 130, 315-325) hold session-slot release until the old assignment settler finishes.
5. **Special relay residue is still present.**
   - `gact/routes/system.py:580` still emits `relay=relay_capabilities(...)` from `app.state.relay_*`.
   - `agent.py:484` and `gact/mcp_gateway_refresh.py:41` still keep `_relay_federation_epoch`.
   - `gact/agents/builders.py:522` still reads `_remote_mcp_federation`.
   - `gact/session_host_agent.py:128` and `gact/routes/providers.py:596` still call `construct_agent_with_relay`.
   - `docs/ENVIRONMENT.md` lines 79 and 233-256, and `scripts/config_key_notes.py` (around lines 100 and 1031+), still document the removed `relay.*` and `CLIO_CHILD_FORWARD_DEADLINE_S` keys. The guard only scans `config.defaults.yaml`.

## P1 – delete, but needs a decision or sweep

6. **Leftover custom executor state in `tools/mcp_executor.py`.** `_accepted_task_handles` (line 255) and `_pending_task_submissions` (line 277) still gate `aclose` at line 576. Nothing populates them now. `mcp_extension_registry.py:208` still lists the deleted `_build_tasks`. The docstring at `mcp_executor.py:78` still references the wait ladder.
7. **`tools/task_receipt.py` keeps old claim policy.**
   - `TaskAwareClient._resolve_claimed_result` is old extension-claim policy. `mcp_runtime.py:480` still makes this class the default client.
   - `accepted_result` hard-codes `kind == "MCP"` and a `task_` handle prefix.
   - `validate_terminal(record, current)` takes the old record shape, and the retained `_resolve_claimed_result` validates against the current schema through `session.validate_tool_result`.
   - The plan says to keep only the local receipt type and strict raw-schema validation.
8. **Storage still carries recovery that interrupts surviving provider jobs, plus task-row mirrors.**
   - `gact/storage/store.py:116` `recover()` is called from `StorageService.__init__` (`service.py:78`). It marks every queued or running operation as interrupted, including Globus jobs.
   - `TransferOperation` keeps `native_request`, `task_handle`, `owner_session_id` and `invocation_id` (`models.py:175-185`).
   - `StorageService.require_idle` (`service.py` around line 230) keys on `native_request`.
   - `execute_transfer` (`service.py:383-429`) is a storage-owned poll loop with `asyncio.sleep(5)`.
   - `routes/connected_storage.py:619-722` still use the deleted `validate_task_owner`, `submit_source_action`, `source_operation_views` and `cancel_selected`.
   - The plan lists these storage items for deletion, but the commit did not touch `service.py`, `store.py` or `models.py`.
9. **Wait and spawn presenters for the old tool names remain.** Examples are `gact/agents/native_presenters.py:36,52` (`build_wait_tool`, `waiting_presentation`) and `tool_instrumentation.py:144` (`_wait_agent_tasks_call_metadata`). The child-error vocabulary in `turn_spawn_failures.py` is tied to `ERROR_REASONS` from `agent_tasks`.
10. **The `assignment_disposition` plumbing in `gact/agents/clio_react_submit.py:93-109` still targets the deleted `set_assignment_disposition`.** It is the finite-assignment decision path and needs the new owner.
11. **About 64 test files still import removed modules.** Several are wholly architecture-bound and should be deleted now, because the plan says to delete architecture-bound tests:
    - `test_jarvis_jobs`
    - `test_jarvis_boot_preload`
    - `test_remote_mcp_federation`
    - `test_mcp_wait_semantics`
    - `test_spawn_ensemble_s5`
    - `test_invoker_s7`
    - `test_live_handle_1037`
    - `test_agent_task_*`
    - the fixtures `tests/fixtures/{background_exit_part_1131,message_agent_parts_1128,run_handle_parts_1127}.json`
    - `tests/schema_expectations/invoker_wire_shapes.json`

## P2 – non-task algorithms and behaviors lost that the ledger doesn't track

The ledger must gain rows for these, or the rebuild will silently drop them. Recoverable from `5475042f`.

- **Workspace single-writer proof.** `gact/artifacts/versions.py:552` still calls the deleted `_workspace_single_writer`. It returned dirty on any ambiguity, which is a safety property, so the replacement must not default to clean.
- **Storage security checks in the deleted `storage_server.py`.**
  - `prepare_download` bounded selected paths to 1–1000 relative paths and ran the permission gate.
  - `execute_storage` rejected a source whose selection or access changed after submission.
  - `storage_result` returned a credential-free projection.
  - `validate_task_owner` checked workspace ownership.
  - `submit_source_action` handled authenticated human source actions.
  - Only W03 (`index_inputs` dedupe) is in the ledger.
- **`AsyncMCPToolExecutor.call_tool_result` was deleted wholesale.** It also held:
  - the uncertain-mutating-timeout retry block,
  - spawn-diet first-call learning,
  - `typed_mcp_call_error`, which handles MRTR exhaustion,
  - `_connected_namespaces` tracking.

  Its callers `execution.py:763`, `external_mcp_calls.py:85`, `mcp_apps.py:557` and `mcp_app_routes.py:131` are now dangling.
- **Non-task parts of `turn_forward.py`.** `forward_turn`, `_run_module` and `_run_turn_setup_off_loop` were deleted. They carried:
  - the workspace-lease phase and async tool-session context,
  - `turn_start_notices`,
  - `native_input_kwargs`,
  - the contextvar copy for turn injections,
  - off-loop cold MCP setup.

  `turn.py:86`, `turn_prologue_guard.py:65` and `turn_finalize_goal.py:40` still import them. `StepRecorder.carry_over` also did general context recovery for non-task sessions.
- **Question-ledger safeguards.** `claim_question_transition` (the atomic answer-versus-timeout arbiter), `restore_user_questions` and `stamp_question_routing_fields` are still imported by name in `elicitation_bridge`, `agent_elicitation_dispatch`, `variant_close` and `question_answer_message`. The ask_user deadline helpers are also gone (`ask_user_expires_at` is still used by `variant_drafts.py:424`).
- **Features with no ledger row:**
  - the spotter-ai watcher arm/disarm (`spotter_watcher.py`),
  - skill-spawn and blueprint commission (`skill_runtime.py:699`),
  - goal redrive, waiting-budget expiry and `launch_pending_goal`,
  - `refuse_parked_inputs`, which refused and retained pending inputs after an agent init failure,
  - parent-turn reasoning inheritance (`turn_reasoning.py:145` calls the deleted `_parent_turn_reasoning`),
  - the `@agent_run` context references,
  - the `subagent.upserted` ancestor path,
  - `purge_session_tasks` on session delete,
  - child-artifact return (`agent_task_artifacts.py`),
  - the bounded child-output digest with verbatim fetch (`agent_task_output_digest.py`),
  - `descendant_walk`, used by session export and provenance.
- **`recover_pending_feedback`.** It migrated pending legacy steers from `message_intents` into Core. F04 doesn't name human steers explicitly.

## Guard gaps

`scripts/check_task_replacement_removal.py` has the following gaps:

- It never detects undefined names. This commit left dozens of dangling references, such as `restore_user_questions` at `app.py:2161`.
- It scans neither generated docs nor `scripts/config_key_notes.py` for removed config keys.
- It has no entries for `task_store`, `user_questions`, `pending_loop_inbox_drain`, `automatic_input_hold`, `relay_capabilities` or `_remote_mcp_federation`.
- It has no check for relative imports.

I'd run a static undefined-name check, such as ruff F821 or pyflakes. It's a build-adjacent step, so I didn't run it. Use it only to list the missing bindings. Don't stub them.

## Expected breaks that are not findings

These are legitimate missing bindings, to be rebuilt, not retained authority:

- `app.py` imports of `install_turn_runner` and `drain_app_turns`.
- `server_boot` task-host startup and shutdown.
- `composer_runtime` idle hook.
- The deleted `register_*_routes` calls.
- Native configuration keys that have no reader yet.

## Rebuild requirements, not removal fixes

- Convert the blocking queue and lock waits in the Codex direct and Claude session bridges to asynchronous waits or session-owned execution. The commit didn't touch `providers/`.
- Session-exclusive ownership until worker exit.
- Decide who owns the Globus polling cadence.
- Replace the dependency on the `agent_task_registry` structure in the session `agent_task` metadata block, the `session_type == "agent_task"` check and `automatic_input_hold`, once the Core snapshot exists.

## Implementer disposition

Cleanup of the exact c1 review cache above was rejected by automatic approval review as blocked by policy. The guarded removal command did not run. That root is now manual-only: no retry, parent removal, move or alternative helper. Its absence is unverified. The CLI review controller ended with exit0 and confirmed original authentication unchanged. This is recorded in task-replacement-cleanup-receipts.json and is not a completion receipt.

Correct the surviving owners/callers and guard; restore the independent general context-recovery algorithm. Explicitly retain the non-task behavior lessons in the ledger. Typed external-input payload markers are not themselves execution authorities. Provider polling inside the real native-owned transfer body is a retained workload algorithm, not a second generic task scheduler. Remove blanket storage recovery and native-row mirrors. The next reviews must check these distinctions against source. A passing denylist does not authorize rebuilding or release.
