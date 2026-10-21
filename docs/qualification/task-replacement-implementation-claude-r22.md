# Source verdict for core b9765992: NO-GO

I read only; nothing was run. I traced the R21 paths against both R20 reports. Most R20 findings are now closed in source, but D1–D5 below are concrete defects that should block. Behavioral tests, CI and the live matrix are unexecuted for this packet, so there is no runtime qualification and I make no completion claim.

## Blocking defects

**D1. Orphan-call closure only works for the last step, so recovery can raise.** `context_identity.py:83-102`
- The synthesized "outcome uncertain" observation always gets `order` and `logical_time` of max+1, so it lands at the end, after all later segments.
- `fold_steps` requires a result to sit in the same open step as its call (`clio_react_record.py:255-258`, `302-305`).
- If any thought or user segment follows the orphan call, folding raises `unanswered_call`. The validating `fold_steps` at `context_identity.py:121` fails, and the forward fails on every attempt.
- The common transcript case is a stopped or crashed tool call followed by a later user turn, then a restart.
- Cold folding sorts by `(order, logical_time)` (`context_view.py:153`), so publishing without validation would not help.
- Fix: place the observation immediately after the step that owns the call. Use fractional `order`, and check whether `ContextView` sorts by `logical_time` (`context_view.py:216`).

**D2. Cancel-delivery retries never retire after the owner's resources close, so shutdown can hang.**
- Affected code:
  - `external_task_controls.py:397-419`
  - `external_tasks.py:507-516`
  - `native_task_settlement.py:289-305`
- R21 retired only the "no bound call" spin. A bound call whose transport is closed or unreachable still raises on every retry, and the entry stays pending.
- `CoreRecovery.drain()` loops until the pending set is empty (`core_recovery.py:55-58`).
- `close()` runs `external.close()` before `drain()` (`task_runtime.py:402-411`). Native `__aexit__` leaves `_calls` populated (`native_tools.py:152-164`).
- The reconnect paths already return True when closing or `_resources_closed`; the cancel-delivery paths don't.
- Fix: retire delivery when closing. The durable intent stays, and the next `restore` re-arms it.

**D3. External uncertain observations aren't deduplicated.** `external_tasks.py:629-647`
- `_attention` writes a new snapshot and event on every call. The native `_uncertain` got the dedupe.
- Examples:
  - Each failed `external-recovery-attention` retry writes a snapshot.
  - Each `observe` of an uncertain stdio or identity-unknown task goes through `refresh_owner`, then `restore`, then `_attention` (`external_tasks.py:188-205`), so a read causes a Core write.
  - Each re-observed terminal reply rewrites the snapshot (`external_task_inputs.py:62-94`).
- This misses the R21 row "Deduplicate identical uncertain observations". It is bounded churn, not a tight loop.

**D4. Workflow reference repair isn't isolated, so one bad root can block startup.** `conversation_recovery.py:76-77`
- `repair_workflow_reference` runs per root with no try/except or deferral, at the top of `_restore_input_projections`.
- Any failure (details validation, session update, writer) aborts `Conversations.restore()`. `_restoring` then stays True.
- In `task_runtime.start` that aborts service startup (`task_runtime.py:378-387`).
- The same function also runs in `ready()` (`conversations.py:111-114`). If it raises there, the exception ends the recovery worker. When `ready()` runs from the post-loop `on_ready` call in `_recover`, that call is outside the try (`core_recovery.py:95-96`), and `drain()` then re-raises at shutdown.
- Fix: isolate each root and defer the failures. This is the same isolation R21 already applied to plan Questions.

**D5. Replay now fails closed on any unreadable historical assignment details.** `task_history_projection.py:281-309`
- For every replayed Session or Subagent snapshot, replay does `read_content` and `AssignmentDetails.model_validate`. It raises on an owner mismatch.
- One unreadable or legacy-shaped details blob makes `restore()` raise and sets `requires_recovery`. The whole task history is then unusable.
- This conflicts with "preserve old data-only checkpoints at startup".
- It also adds a content read per historical assignment snapshot on every replay. The R21 note that Core performance needs measurement applies.
- Fix: make failures non-fatal by marking the root dirty or unresolved instead of raising.

## Defects that depend on code outside the packet

**D6. The context-clear boundary parses timestamps inside the retried approval.** `plan_exit_resolution.py:178-189`
- `datetime.fromisoformat(row.created_at)` is compared with the Question's timezone-aware `created_at`.
- Message timestamps come from `_iso_from_epoch` (`session_store.py:163`), which isn't in the packet.
- If it returns naive strings, `Z` suffixes on Python before 3.11, or empty or legacy values, the comparison raises. Every repair retry then fails and the gate never clears.
- Fix: use ledger position or message identity instead of parsing timestamps.

**D7. Current-turn exclusion only covers `role == "user"` rows.** `context_identity.py:68-76`
- `run_segment` builds continuation rows with `role="system"` and `id == turn_id` (`task_runtime.py:260-277`).
- The transcript decoder turns any non-user text part into an assistant `thought` (`conversation_projection.py:134-141`).
- If such a row is already in the ledger when the forward starts, it is decoded as assistant text. A fresh primary scope also gets a spurious "Recovered…" notice.
- I couldn't confirm that rows are appended before the forward, because `turn.py` isn't in the packet.

**D8. A plan-approval retry can wedge on content drift.** `plan_exit_resolution.py:158-176` with `session_input.py:56-58`
- A retry restages the resume mail under the same identity, and `accept_session_input` raises if the content differs.
- For native Questions the captured artifact and review content make it deterministic.
- On the legacy fallback, `save_approved_plan` can degrade or succeed differently, and `plan_review_content(plan_file)` rereads the file. A changed file or save outcome then wedges the retry.

## Lower-severity notes
- `native_task_settlement.py:249-261`: cancelling a native member whose binding was already retired records "backend acceptance remains uncertain". That overwrites the accurate "Physical settlement is unconfirmed" reason, even though acceptance is known.
- `external_task_controls.py:427-431`: `deliver()` can return early because the call was replaced or the backend is terminal. The caller still reports `external_acknowledged` although no RPC was sent.
- `workflows.py:535-541`: re-entry with the same invocation ID always replays, even for an unfinished execution, and never continues it. A new invocation ID does resume. Confirm that is intended.
- `observe` → `refresh_owner` → `_drive` re-arms `deliver_cancel`. An observer-triggered refresh can therefore re-send a cancel RPC that was already acknowledged. Please decide whether that counts as "passive listeners never issue new cancellation requests".
- Workflow state is rendered under "Launch context" with no size bound and without the "quoted data" fencing that evidence pins get.

## R20 findings checked against R2

| R20 finding | Source status |
| --- | --- |
| Claude 1: passive cancel loop | Closed: `request_members=False` on recheck, native `_uncertain` dedupe. D3 remains for external. |
| Claude 2: endless delivery entries | Partly closed: the no-binding case retires. D2 remains. |
| Claude 3: unknown-attempt attention | Closed: `_settle` raises attention before the terminal-only returns, with one episode. |
| Claude 4: transcript copied into fresh scopes | Closed: variant try skipped, `allow_transcript` limited to the primary scope, epoch scopes skipped. This relies on `session.agent["id"]` matching the primary scope, which I couldn't verify. |
| Claude 5: legacy `recipient_input` | Closed: a missing `schema_version` is treated as unconfirmed. |
| Claude 6: transcript bugs | Thought grouping and post-compaction parts are closed. The `id` and `turn_id` match is closed for user rows only (D7). Unanswered calls are now closed with uncertain observations (D1). |
| Claude 7: plan repair isolation | Closed: each gate repairs independently and defers on failure. The predicates match (`question_events.py:63-65` vs `is_plan_exit_question`). |
| Claude 8, Astra 2: stale pause on restore | Closed: restore checks `agent_paused_assignment`. |
| Claude minors | Closed: timeout overflow is rejected, uncertain cleanup outranks timeout, and cancelling activity survives worker unwind. The restart-attention identity now includes the reason. |
| Astra 1: compaction mid-row | Closed: parts after the last summarization part are kept. |
| Astra 3: deferred-completion deadline | Closed: `complete_deferred` rechecks the deadline and re-arms the timer. |
| Astra 4: old invocation advancing a retry | Closed: exact invocation lookup runs before the latest execution, and replay never advances. D4 and D5 are the exceptions. |
| Astra data handoff | Closed: `launch_context={"workflow_state": …}` is stored in immutable mail and rendered by `render_delegation` at input commit. Re-spawn of an admitted step compares equal content. |
| Astra SDK retirement | Closed for native and external: retirement needs terminal backend evidence, a matching captured identity, the observer exited, and Core not in recovery. Late native settlement uses the captured schema. Refresh reconnects the original identity without `tools/call`. |

Strict R2 is intact: restart still requires confirmed or never-started settlement. External ACK is still not cleanup proof, and nothing relabels uncertainty as cleanup. The optional human exception stays unanswered.

## Missing necessary scope
- Callers of `set_react_scope`, and the `StoredSession.agent` and `metadata_patch` semantics. Needed to confirm that `scope == session.agent["id"]` is the primary scope. A per-message agent override or a blueprint turn would silently skip restoration.
- `gact/runtime/globals.py` (`_iso_from_epoch`, `_active_semantic_turn_id`) and the turn code that appends ledger rows (`turn.py`). Needed for D6 and D7.
- `native_identity.py`, for the new `local_runtime_gone` branch in restore. Previously every memory root went to `interrupted`; now an unknown runtime gets only an uncertainty note.
- ARC `ContextView` render ordering versus `fold_atoms` ordering, to specify the D1 fix.

Also not exercised in this packet: no behavioral case has run for D1–D8, and all CI and live-matrix gates remain unexecuted.
