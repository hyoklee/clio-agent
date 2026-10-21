# Source verdict: NO-GO for the R19 correction packet

I read REVIEW-DIFF.md, the R19 plan, both reports and every changed file. Nothing was run. The C2, C4, C5/C7 and C6 mechanisms are mostly sound, but C8 and C1 each have defects that should block the commit. Findings 1–4 should be fixed before the behavioral tests and CI. Findings 5–8 are real but smaller.

## Blocking findings

**1. C8: the "passive" recheck re-issues cancellation and can feed itself.** `src/clio_agent/gact/conversation_controls.py:517-540,679-704`
- Every rerun of `_cancel_subtree`, including the one `recheck` starts, calls `request_member` again for each non-terminal member. That calls `cancel_work`, so `native.cancel` or `external.cancel` runs again.
- The listener at `:699` fires on any write to a member handle, including writes caused by that rerun.
- `NativeTools._uncertain` (`native_tools.py:738-754`) always writes a new snapshot. The `native-cancel-unknown` path (`native_task_settlement.py:226-236`) and the provider-cancel-failure path (`:192-197`) both call it on every `cancel`.
- So any native member with uncertain acceptance triggers: rerun, cancel, write, listener, rerun. That is the endless receipt-spin C8 was meant to remove.
- Members with a live transport re-send the cancel RPC on every observation write.
- Fix: a passive rerun should only re-read member state. It should not call `request_member` for members whose `cancellation_requested_at` is already set. `_uncertain` should also return early when status, episode and message are unchanged.

**2. C8: endless recovery entries survive, and they block graceful shutdown.** `native_task_settlement.py:226-236,264-275`, `core_recovery.py:55-58`, `task_runtime.py:397-399`
- The diff retires the waiter coroutine but leaves `native-cancel-delivery` as a deferred entry.
- `_deliver_cancel` returns `False` whenever there is no bound live call, so the entry never retires.
- `CoreRecovery.drain()` loops `while worker not done`, and `close()` awaits it. One unresolvable native cancellation therefore hangs shutdown.
- `provider-cancel-reconnect` (`:204-215`) has the same shape.
- Claude's R19 report flagged this as "verify". The diff does not touch it.
- Fix: retire these entries once cancellation intent is durable and no live call exists. Leave later proof to the passive listener and startup recovery.

**3. C8: attention for unknown cleanup is now deferred until the replacement leg is terminal.** `native_task_settlement.py:83-92,104-115`
- Before, `_settle` called `_uncertain("Physical settlement is unconfirmed")` as soon as any attempt was `unknown`.
- Now the `backend_observation is None` and `reply.status not in terminal` early returns come first, so `_uncertain` is reached only when the new leg has a terminal result.
- `_record_reply` (`native_tools.py:612-633`) deliberately stops updating status while an attempt is `unknown`, and relied on `_settle` to raise attention.
- After `lost_attempts` marks attempts unknown at restart (`native_task_recovery.py:117-124`), a working replacement leg now shows a stale `running` status with no attention episode.
- Fix: call `_uncertain` for unknown attempts before the terminal-only returns. Keep the result hiding and the "backend reported X" suffix only when a terminal reply exists.

**4. C1: `carry_over` runs unconditionally, so the transcript fallback can copy the whole session ledger into any fresh scope.** `clio_react.py:367-369`, `context_identity.py:53-62`
- `_arrivals` and `commit_input` both guard on `context.current().react_run >= 0` (`clio_react.py:408`, `clio_react_record.py:422`). `run()` does not.
- `arc_scope()` uses `run_keyed_scope(...)`, so ensemble runs and nested experts get their own absent scope. They have no `arc.op` trace, so `found` is False.
- The fallback then runs `transcript_segments(ledger)` and writes the parent session transcript into that scope.
- That contradicts "never copy predecessor transcripts" and "empty/no evidence remains empty".
- Fix: restore only for the stable primary scope, and skip when `react_run >= 0`. I could not confirm the scope shape because `run_keyed_scope`, `active_react_scope` and the `#epoch:` convention are not in the packet.

## Other defects

**5. C1: the trace fold validates legacy `recipient_input` records that the Core scan skips.** `context_restore.py:48-52` against `task_history_projection.py:321-322`
- `_scope_inputs` skips segments without `schema_version`, as historical-migration data.
- `recorded_segments` calls `RecipientInput.model_validate` on every `recipient_input`.
- A trace containing a legacy-shaped record raises, and the forward fails on every attempt.
- Fix: treat a missing `schema_version` as unconfirmed or historical, as `_scope_inputs` does.

**6. C1: transcript reconstruction bugs.**
- `conversation_projection.py:131` uses `if not calls:`, so each text or thinking part before the first tool call opens a new `thought`. A `[thinking, text, tool_call]` row becomes two consecutive assistant messages, and the thinking has no continuation data. The `thought is None` guard below it shows the intended condition is `if thought is None`.
- `context_identity.py:58` excludes the current turn only by `row.id == turn_id`, while `retained_turns` uses both `id` and `turn_id`. If the row id differs from the turn id, the current input is restored and then written again.
- `context_identity.py:85` tests `not restored`. A fully tombstoned scope still yields tombstones, so it gets a live "Recovered…" notice written. Test for live segments instead.
- `conversation_projection.py:192`: an unanswered call in the transcript path raises permanently, unlike the trace path, which synthesizes uncertain observations. The plan accepts failing loudly, but there is no escape from a session that was interrupted mid-tool.

**7. C2: repair isolation and predicate mismatch.**
- `question_events.py:88-92`: `resolve_plan_question` is called with no per-session handling. One failure aborts `restore()`, so `ready()` and `signal_pending()` never run for any session (`conversations.py:111-115`, `task_runtime.py:371-372`). Wrap each session and `defer` the failures.
- `question_events.py:45-47` uses `source == "plan_exit" or metadata.plan_exit_approval`, but `resolve_plan_question` uses `is_plan_exit_question`. If those differ, a cancelled or expired plan Question is not repaired until restart.
- Release latency is at least 1 second, because `CoreRecovery._recover` sleeps first.
- `resolve_plan_exit_answer` now runs plan saving, ledger replacement and playbook transition under the global `task_history._lock`. A crash between staging and clearing the gate re-runs these non-idempotent steps. The one-time mail depends on `accept_session_input` deduplicating `steer_message_id`, which I could not see.

**8. C4: restore binds a stale hold to the successor.** `conversation_recovery.py:107-113`
- It sets `_paused[sid] = task.handle` whenever `agent_paused` is true, ignoring `agent_paused_assignment`.
- `model_paused` correctly ignores a hold bound to another handle, but restore overrides it.
- Narrow window: it needs a crash after the successor is created but before `clear_pause`.
- Fix: bind only if `agent_paused_assignment` is empty or equals `task.handle`, or if `activity == "paused"`.

## Minor
- `workflows.py:592-596`: a huge finite `timeout_s` raises `OverflowError` at spawn, after parsing accepted it. Bound it in `_parse_step_timeout`.
- `workflows.py:641-647`: `deadline_exceeded` takes precedence over the uncertain-settlement check. A terminal child with unknown settlement is reported as a step timeout. A parent cancel after the deadline is also reported as a timeout.
- `conversations.py:631-639`: `stopped()` can overwrite `cancelling` with `paused` on a paused-then-cancelled assignment. This is cosmetic.
- `conversation_controls.py:457`: the deterministic `restart-attention:<handle>` id suppresses any later restart failure reason.

## Verified as correct
- **C2:** plan-resolution mail is staged before the gate clears. The gate is re-checked under the lock. Answer, cancel and expiry all reach the resolver, and the answer path is idempotent on retry.
- **C4:** pause captures the exact reservation and rejects a cancelling assignment. Resume writes deterministic mail before clearing the hold, and is a no-op when no hold exists. `clear_pause` is compare-and-clear on the handle.
- **C5/C7:** the saved row is consulted before the gate. `merged` is persisted with the state, and legacy rows are handled. Only a known-settled failure finishes the checkpoint. Retry reuses merged rows by reference and spawns under a new id.
- **C6:** the deadline is persisted in the initial details before child mail, enforced by one owner-local timer through `cancel`, and survives parent Stop. It is re-armed on restore, retired on terminal states and shutdown, and re-armed early timers are rechecked. NaN, infinity and zero are rejected.
- **C8 evidence:** nonfinal backend output returns `pending=true` with `evidence_is_final=False` and no terminal timestamp. `_collected` only acknowledges `pending is False`, so no collection happens. Fresh receipts do not settle an old incarnation.
- **Strict R2:** `eligible` blocks mail while a cancelling assignment is non-terminal, and `restart` requires known settlement. The natural-external-ACK policy and the pending human amendment were not touched.

## Unreviewed required production scope
These were outside the 40-file packet, and the corresponding claims cannot be accepted until they are reviewed:
- **ARC and context plane:**
  - `has_segments`, `restore_empty_context` and `list_segments(include_tombstoned)` on both ARCMemory and HistoryPlane.
  - `fold_atoms`, and the shape of `arc.op` trace payloads (`logical_time`, any truncation).
  - `semantic_trace_backend.session_events`.
  - The scope naming that includes `#epoch:`.
  - Whether History mode implements `restore_empty_context` at all.
- **Plan and Question routes:**
  - `session_input.accept_session_input`.
  - `routes/plan_interactions.is_plan_exit_question`.
  - `plan_mode`, `plan_reuse.save_approved_plan`, `planning.transition_playbook_to_execution`, `deps.replace_session_messages`.
- **C3 callers:** whoever calls `QuestionCommands.visual_question`. Its signature has no exact-ID parameter, so "exact open ID works, second click fails, no feedback mail" cannot be verified from the diff.
- **Native and persistence:** the native driver and `_record_reply` write frequency, which determines how bad finding 1 is, and `native_work.now` timestamp format, which the deadline comparisons assume is timezone-aware.

No capacity failure was treated as a product bug. Behavioral tests, CI and live qualification remain separate and should wait for fixes to findings 1–4.
