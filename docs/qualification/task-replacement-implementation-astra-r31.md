**Architecture: GO on the ownership design. Source: NO-GO. Qualification: NO-GO; fresh execution remains pending.**

Reviewed committed core `3d929627c2207b5e9c14bf525f9474f5059d34b8`, GACT `30df56ed9556a99fbac6a4984374adbfd46d82eb`, and marketplace `9257bba5953b012ba796299df4c633e698dbaddc`. I found five actionable issues.

1. **[P1] Stop can miss the input hold and immediately restart the same input.**

   [`Conversations._run`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:652) awaits the initial `busy` write **before** entering its cancellation handler. If Stop cancels that await, the handler never marks the exact uncommitted trigger held. [`TurnRunner._pump`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_runner.py:135) releases the reservation and considers admission again; the original input remains eligible, so it can restart without a later arrival.

   Finalization also sits outside that cancellation handler, leaving another activity-reconciliation gap.

   **Correction:** Reconcile the exact trigger and activity at the existing reservation-retirement boundary, including cancellation before body entry and during finalization. Preserve the input for a later eligible arrival. The existing preflight Stop regression covers composer promotion, not this admitted-segment window.

2. **[P1] A completed Stop approval can leave a gate that recovery refuses to release.**

   [`complete_deferred`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:378) records terminal completion before [`turn_approval.complete`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/turn_approval.py:314) clears the session gate. A crash or failed session update between these operations leaves a completed assignment with its approval gate installed.

   On recovery or answer retry, `resolve()` calls [`restore_gate`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/turn_approval.py:137), which rejects terminal assignments. The gate therefore cannot finish releasing, and subsequent input remains blocked.

   **Correction:** Recognize that the frozen approval’s exact completion already landed, then idempotently release only its matching gate. The existing effect-before-release recovery test uses `UserPromptSubmit`; the Stop test replaces `complete_deferred`, so neither covers this failure.

3. **[P1] Previous pause/resume can prevent cancellation from clearing an approval gate.**

   Resume writes `agent_paused_assignment=""`. Cancellation’s [`clear_pause`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:729) calls `release_cancelled_assignment_gate` only when that metadata equals the cancelled assignment. An existing empty string fails this condition.

   Consequently, pause → resume → pending plan/hook approval → cancel can settle the assignment while retaining its execution gate. The Question resolver also refuses the cancelled assignment, so later human input stays ineligible.

   **Correction:** Release the matching cancelled assignment’s Question gate independently of pause-token cleanup. The gate helper already checks assignment ownership; it does not need the unrelated pause condition.

4. **[P2] Native Question media still disappears in cross-session collection and recovery.**

   [`_commit_collection`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:688) renders only Question notices present in `staged.items`. An authorized parent or peer can explicitly collect a Question without subscribing, but [`_collected`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:67) publishes notices only to the owner and subscribers. That reader therefore receives serialized attachment metadata without native media.

   There is also an owner recovery gap: after a failed recipient-input commit, [`commit_input`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:421) treats the observation’s notifications as already collected. Staging skips their injections, so the retry can acknowledge them without rebuilding their native rendered content.

   **Correction:** Derive Question rendering from the authorized collected results, independently of automatic-notification membership, and preserve that rendering during commitment recovery. Keep the common recipient-input boundary. The new media tests cover successful owner delivery; they inspect retained references rather than these peer/recovery paths.

5. **[P2] The new approval admission check scales with lifetime session history.**

   [`eligible`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:171) intersects active Questions with `session_handles(sid)`. [`session_handles`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:592) copies every retained task handle for that session—even when there are no active Questions. Staging repeats eligibility checks for pending inputs.

   This is a specific hot-path indexing defect, distinct from the permitted full startup replay.

   **Correction:** Perform the narrow intersection inside the existing history owner using its underlying indexes, without copying lifetime session history for each input. Preserve unlimited canonical history. The existing bounded-read regression exercises `TaskOperations.query`, not admission or mailbox staging.

The architecture remains substantially better aligned with R2. Stable sessions and finite assignment handles are distinct; authorization checks immutable lineage and explicit grants; peer messaging rechecks delivery rights; waits use observation notifications; declared workflows use ordinary child assignments, shared waits and retained checkpoints. Questions remain under `QuestionCommands`, with collection acknowledged through recipient-input commitment. I found no reintroduced generic scheduler or competing task registry in the inspected paths.

The latest corrections also materially improve the source: SDK entry and exit now share the application lifespan task, Stop approvals retain exact output, plan posting installs its gate before becoming answerable, human self-waits work, and whole-tool liveness polling is removed.

These findings call for bounded corrections in those owners. Qualification still requires fresh behavior cases, the real SDK lifecycle retry, F03 measurements, current-revision CI, and Q1–Q9/R1–R6 acceptance. Earlier reports and static checks do not establish those outcomes.

I made no edits and ran no tests, services or models.
