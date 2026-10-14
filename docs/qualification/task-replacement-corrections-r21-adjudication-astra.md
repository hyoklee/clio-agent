**Yes—the workflow proposal uses the correct existing-owner seam. C8 is also sound in principle, but changing the retirement predicate alone would break late settlement.** This is design approval for the next correction packet, not implementation acceptance.

For **historical workflow lookup**, keep these boundaries:

- Key the lookup by **root assignment and invocation**, with immutable execution identity and validated request/declaration identity. Record the binding when a new invocation resumes an existing execution too.
- Confirm checkpoint content, then its provenance observation, then rebuildable projections. A crash between those writes must repair the exact-invocation index and latest reference before admitting more work. The existing [confirmed writer](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:713) and [replay/index repair](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history_projection.py:37) are the appropriate locations.
- An exact historical lookup must return that execution’s recorded outcome **without passing through the current unconditional `save()`**, advancing another execution, or replacing the latest pointer.
- Populate historical lookups for existing retained checkpoints during startup replay. Otherwise adding the new observation type fixes only future executions.

`AssignmentDetails.workflow` can remain a passive latest reference. No workflow engine, separate database or metadata history map is needed.

For **C8 retirement**, the essential generic custody data already exists in Core: captured tool/version/schema/arguments and submission identity, accepted backend identity, raw terminal response, and per-incarnation cleanup evidence. See [SubmissionContext and NativeAttempt](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/arc/task_types.py:166). I found no missing generic field that requires another custody store.

The necessary corrections are:

1. **Make late native settlement independent of `AcceptedNativeCall`.**
   [_settle currently returns when that object is absent](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_task_settlement.py:91). Load the captured contract from the exact confirmed submission instead. A later cleanup receipt must still finalize the task and wake the parent after SDK retirement.

2. **Retire only after durable custody is confirmed.**
   Require the recorded terminal observation to match the binding being removed, observer/RPC exit, and no outstanding adoption or recording evidence that exists only in memory. Preserve active cleanup ownership, cancellation holds, incarnation records and the passive parent listener. Do not carry over the current unconditional `_control_holds.discard()` into uncertainty retirement.

3. **Finish obsolete cancellation-delivery retries.**
   [_deliver_cancel](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_task_settlement.py:264) currently returns `False` when the binding is absent. After retirement that can keep `CoreRecovery` running indefinitely. A confirmed terminal backend observation should retire that delivery retry while leaving physical settlement unknown.

4. **Provide a concrete existing-owner reconnection path.**
   Public [observe](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:281) currently reads Core; it does not reconnect. Reuse the existing identity-bound recovery machinery for an explicit refresh, without another `tools/call`, automatic resubmission or permanent polling.

One qualification: **Core alone is not sufficient for every reconnection.** External recovery still needs matching trusted configuration and credentials; [_recovery_client](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/external_tasks.py:272) correctly rejects a mismatch. Provider cleanup also depends on the existing durable operation record containing provider identity and job/publication facts, as [recover_provider](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_storage.py:264) demonstrates. Preserve those owners and records; do not duplicate them into a new supervisor.

Reviewed frozen `f020a591`; no edits or execution.
