# Independent Astra source review R30

Read-only review of committed core `cf583134` / GACT `30df56ed`; no model or runtime acceptance claim.

**Source verdict: NO-GO for core `cf583134a84e4202e23acf5bb783872789c96d7a` / GACT `30df56ed`.** I found five actionable issues. These are source-derived failure paths, not runtime reproductions.

1. **[P1] Explicit completion bypasses a pending Stop-hook approval.**
   `_finish_segment` includes `execution_gate` when calculating outstanding work, but then lets `outcome.disposition == "complete"` override that calculation. The model can request this through the shipped `submit` tool. Stop hooks run before this final assignment update, so a hook can create a pending approval and the assignment can nevertheless become terminal immediately afterward. A parent’s shared wait then returns completion and can advance its workflow before approval.

   **Fix:** Treat the pending completion gate as a veto on assignment completion. Preserve explicit completion’s ability to leave ordinary background work running.

   Evidence: [completion selection](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:247), [model disposition propagation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn.py:612), [Stop-hook dispatch](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_finalize.py:592).

2. **[P1] A recovered Stop approval can complete with an older output—or become permanently stuck.**
   The durable hook binding captures the assignment and context epoch, but no reference identifying the particular output awaiting approval. That turn’s `last_output` is written later, in `_finish_segment`. A crash after Question creation but before that write leaves the approval durable while `last_output` is absent or belongs to an earlier segment of the same assignment. On approval, `complete_deferred` accepts whichever `last_output` exists. An absent value raises an error after the Question is already answered; an older value can be published as the completed result.

   **Fix:** Retain and bind the exact deferred turn’s output before exposing its approval. Recovery must report unresolved evidence when that output cannot be established.

   Evidence: [hook binding](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/turn_approval.py:25), [later output recording](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:259), [completion’s output selection](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:310).

3. **[P1] Plan approval still has a create-before-gate race.**
   `plan_mode` creates and publishes the Question, exits the writer lock, and only afterward installs `execution_gate`. An answer arriving in that interval is durably accepted, but its resolver returns because the gate does not match. The creator can then install a gate pointing to that already-answered Question, leaving the session blocked. A crash in the same interval also leaves no reconstructed plan gate: startup reconstructs missing gates only for `hook_defer`.

   **Fix:** Give plan approval recoverable gate installation and an explicit check for an answer accepted during installation. Apply the decision through the existing Question resolution path.

   Evidence: [creation and subsequent gate write](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/plan_mode.py:565), [resolver’s early return](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/plan_exit_resolution.py:65), [startup reconstruction](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/question_events.py:124).

4. **[P2] Ordinary Question answers retain attachments but do not deliver their native content.**
   GACT’s composer sends `parts` through `answerQuestion`, and the backend validates and stores them. However, automatic `question_answer` delivery serializes the reply as JSON. The model-input renderer invokes native attachment/reference enrichment only for `human` and `composer` items; Question answers take the generic text branch. Explicit shared waits likewise return the serialized result. An image answer therefore reaches the model as attachment metadata rather than image input; resource answers miss the normal enrichment path.

   **Fix:** Render attachment-bearing Question replies through the existing authorized native-input preparation before the common recipient-input commit, including explicit collection.

   Evidence: [composer answer submission](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/hooks/use-session-mutations.ts:273), [attachment acceptance](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/question_surface.py:127), [model rendering branch](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:441).

5. **[P2] Human callers cannot wait for their own session’s active assignment.**
   The HTTP wait route supplies an authenticated human caller with that session ID. `_outcomes` rejects any active Session/Subagent owned by the caller’s session as `cannot_wait_for_own_active_assignment`, without checking `human_action`. The model deadlock safeguard consequently rejects a legitimate external human wait.

   **Fix:** Restrict the self-wait rejection to agent execution callers.

   Evidence: [human caller identity](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/tasks.py:129), [shared wait rejection](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:281).

The replacement’s ownership structure is substantially clearer. The old registry, supervisor, child-forwarding and competing completion-wake modules are removed. Sessions and subagents share assignment execution; peer messaging rechecks grants at delivery; declared workflows use ordinary child assignments and shared waits; Questions use the common records and waits; native task polling remains with the SDK. Those are meaningful simplifications.

The remaining blockers concern ordering and preserved behavior across those boundaries. They should be corrected within the existing conversation, Question and input-rendering owners.

I made no edits and ran no tests or services. Reported lint/type results do not establish these behaviors. Required CI, crash/recovery, physical cancellation, model/workflow and rendered desktop/phone acceptance remain unverified by this review.
