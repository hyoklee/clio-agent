# R19 adjudication: C8 split, other items conditional GO

I read the R19 packet, the R2 plan, the R18 report and the seven-file source subset (`conversation_controls`, `conversations`, `workflows`, `native_task_settlement`, `native_task_recovery`, `external_task_inputs`, `task_types`). Nothing was run. The C2 Question resolver, `task_operations`, `external_tasks.py:740-777`, `native_tools._uncertain` and `conversation_recovery`/`assignments` were not in the subset. Items that depend on them are marked *verify*.

## Verdict

- **C8:** GO for the part that needs no amendment. NO-GO for human continuation until a human makes the one contract decision below.
- **C2, C4, C5/C7, C6:** conditional GO with the changes listed.

## C8: intentional strict contract (keep)

- **External cancel then terminal report.** An external terminal reply after a cancel request stays `task_state_uncertain`, with no `terminal_at`, `settlement="unknown"` and `result=None` (`external_task_inputs.py:80-92`).
- **Fresh receipts.** A fresh receipt never settles an old incarnation (`native_task_recovery.py:117-124`, `native_task_settlement.py:83`).
- **Parent state.** A parent never becomes `cancelled/confirmed` or restartable while a necessary member is unresolved.
- **Holds.** The cancellation intent and admission hold stay. Human input stays Core-pending.

## C8: actual defects

1. **The cancel control parks forever.** `_cancel_subtree` ends in `await changed.wait()` (`conversation_controls.py:568`), and `Conversations.shutdown` awaits every control (`conversations.py:756-759`). One unresolvable external member therefore blocks graceful shutdown. R2 reserves "ends with uncertainty" for human process force-close, not for this wait.
2. **Natural external terminals are judged unsettled.** A member that reached `external_acknowledged` without CLIO ever requesting its cancellation is still treated as uncertain (`:487-505`). That is R18's second route, and R2 says already-terminal outcomes stay historical.
3. **The persistent-native fresh result is hidden.** `_settle` returns at `:83-85` before it ever reads `backend_observation`.
4. **The user has no actionable path.** `restart` fails with a bare "remains uncertain" and names no handles.
5. **Retry entries may never retire** (*verify*). A deferred `native-cancel-delivery` returns False forever if the backend has already reported terminal.

## C8: design changes

**Non-amending part (GO):**

- **Settled predicate.** A member counts as settled if it is terminal and either its settlement is `confirmed` or `never_started`, or its settlement is `external_acknowledged` and `cancellation_requested_at is None`. Keep `interrupted/unknown` unresolved.
- **Exit instead of parking.** When the parent's own retirement is done and every unsettled member is in the `uncertain` list, none is progressing. In that case record the single attention episode and return. Replace the parked wait with a passive `history.listen(handles=members)` callback. It relaunches `_cancel_subtree` through `retain_control` only if no live control exists, and it is removed when the parent turns terminal or at shutdown.
  - A late genuine receipt still finalizes the parent.
  - A late final notice still reaches the successor. The own-subtree retention in `eligible` (`:207-215`) only applies while the parent is the latest assignment.
- **Inspection.** Read-only inspection needs no amendment and the hold stays. Set the uncertain parent's `supported_actions` to `observe, wait, message, cancel, restart`. The attention text lists each member's handle, episode and raw backend status.
- **Persistent native, old incarnation.** Recording the backend completion together with a separate unresolved-settlement state is sufficient to *inform* the user. It is not sufficient to *finish*.
  - Keep per-attempt `cleanup_state="unknown"`.
  - While unknown attempts exist, record "leg N reported `<status>`; incarnation X cleanup unknown" as a provisional observation. Keep `terminal_at=None`, `result=None` and no collection acknowledgement. `get_task_result` returns it labelled unsettled (*verify* in `task_operations`).
  - The only finish is a late receipt bound to that exact incarnation, which lets the existing `_settle` complete with real proof.
  - Retry is a deliberate new invocation with a new handle. The old task stays unresolved.
  - Do not give the member task a terminal state on human say-so. That would be a second, larger R2 amendment.
- **Retry entries.** Retire the deferred cancel-delivery entry once a terminal backend observation is recorded (*verify*).

## C8: human contract decision — required

Inspection and the retained hold are already R2-consistent. Continuation is not. R2 says "Restart requires known necessary cancellation settlement" and "Restart does not bypass unsettled cancellation". The only human-ends-with-uncertainty precedent is process force-close.

**Decision to put to the human:** may an explicit, human-only disposition, enumerated by member handle and attention episode, release `restart` for a cancelled assignment whose members have unknown settlement?

Recommended smallest form:

- **Where it lives.** It is a parameter on the existing `restart`: `accept_unresolved={member: episode}`. It requires `caller.human_action`. It must exactly match the currently unresolved set, so later uncertainty is not swept in.
- **What it records.** It writes `AssignmentDetails.accepted_unresolved` (who, when, handle, episode) on the parent only.
- **Parent terminal state.** The parent closes as `cancelled` with `settlement="accepted_unresolved"`, never `confirmed`. `restart.create` accepts that value only when the record is present and the caller is human.
- **Members.** Member records are untouched. They stay uncertain, with no terminal timestamp, no acknowledgement, and no cleanup claim. The successor's restart mail lists them.
- **Parent timestamp.** The parent receives a terminal timestamp. That is the single bend of R2's text, and the successor model needs it.

If the human declines, the strict fallback is that the parent stays retired and inspectable and can still finalize on real proof. Continuation is then only via a new session.

## C4: conditional GO

- **Bind the hold to the assignment.** Make `agent_paused` hold the assignment handle and `_paused` a `dict[sid, handle]`. A legacy `True` applies to the latest non-terminal assignment only. `eligible` and `stopped` apply the hold only when the bound assignment is the latest live one.
- **Pause races.** `pause` must reject a cancelling assignment. Today `settle()` (`:78-100`) overwrites `activity="cancelling"` with `paused`. Recheck the latest assignment before each write, and compare-and-clear after the metadata write.
- **Clearing.** In `_cancel_subtree.finish` (`:570`), compare-and-clear only `_paused[sid]==handle` and the matching metadata. Do not touch composer, goal or `execution_gate` keys.
- **Resume.** Make it a no-op, with no snapshot rewrite and no mail, when no hold exists for the handle.
  - Fix the ordering defect: `resume` clears the hold at `:148` and writes the mail at `:185`, so a crash in between loses the wake.
  - Write the mail first with a deterministic id and a presence check, then clear the hold, then signal.

## C6: conditional GO

- **Persisted field.** Add `AssignmentDetails.execution_deadline` as an epoch float with `gt=0, allow_inf_nan=False`. Set it through `initial_details` at spawn.
- **Parser defect.** `_parse_step_timeout` accepts NaN and inf, because `value <= 0` is False for NaN (`workflows.py:212`). Require `math.isfinite`.
- **Zero wording.** The packet's "zero remains unbounded" contradicts the loader, which rejects an explicit zero. Keep the rejection, treat absent as unbounded, and fix the packet wording.
- **Timer.** Use one `loop.call_at` handle per assignment in a dict inside `Conversations`, not a task. I found no simpler existing mechanism. `CoreRecovery.defer` is retry, not time-based, and schedules are mailbox producers.
  - On fire, recheck the wall clock and the terminal/cancelling state. If it is early, re-arm.
  - Call `Conversations.cancel`, not `_cancel_subtree` directly, so the intent and admission hold are recorded first.
  - Attribute the notice as `execution_deadline`.
- **Lifecycle.** Arm after the child record is durable and at restore from the active-only handle index. Disarm in the terminal writers and at shutdown. Successors do not inherit the deadline. The deadline is wall-clock and includes pause and downtime. Say so in the doc.
- **Workflow.** Drop `step.timeout_s` from the wait (`workflows.py:566-568`). Report `workflow_step_timeout` when the child is cancelled with `cancellation_requested_at >= execution_deadline`. No new field is needed for that.

## C5/C7: conditional GO

- **Row check first.** Check the saved row before the gate, and evaluate the gate only before spawn (`:543` vs `:553`).
- **Merge flag.** Persist `merged` on the row in the same checkpoint write as the state merge. Rebuild `completed` from merged rows. This also stops the final re-call from remerging (`:594`).
- **Legacy rows.** A row with no `merged` flag counts as merged iff a later step has a row. Otherwise remerging is idempotent.
- **Failed-finish rule.** The current code treats every non-completed terminal child as failed (`:578-585`). Finish the checkpoint only when the child's settlement is `confirmed` or `never_started`. An uncertain-settlement child stays resumable and returns `task_state_uncertain`. Otherwise retry would replay an uncertain operation.
- **Retry.** A new invocation id after a finished failure creates a new execution with `previous` and `retry_of` links.
  - If the declaration and request are identical, carry forward the completed, merged rows by reference and respawn only from the failed step. This avoids replaying side effects.
  - Otherwise start a fresh execution.
  - The same invocation id reads history.

## C2: conditional GO at design level only

- **Order.** Write the deterministic resume mail first, then compare-and-clear the gate. The reverse order loses the decision on a crash.
- **Gate identity.** The gate must carry its Question handle so "clears only its own gate" is checkable (*verify*).
- **Rejection risk.** `eligible` vetoes all mail whenever `execution_gate` is set (`conversations.py:173`). If rejection keeps that gate key, its feedback mail is stuck, which is the same wedge as C2. Confirm planning mode is not the same key.
- **Repair placement.** Run the repair in `ready()` (`:108-113`), after `questions.restore()` and before `signal_pending()`, and as a `recovery.defer` on recording failure.
