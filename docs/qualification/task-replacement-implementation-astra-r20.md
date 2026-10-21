# Independent Astra source review R20

Frozen production f020a591. No tests or services; source review only.

**Confirmed at frozen `f020a591`: this is an additional [P2] retained-behavior regression.** The source NO-GO stands.

The runner merges A’s output into `execution["state"]`, but [the next spawn](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/workflows.py:585) passes only the step description, request, workflow identity and deadline. It supplies no `launch_context`.

There is no downstream repair:

- [render_delegation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/assignment_evidence.py:98) renders launch context only when supplied.
- [Child creation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_runtime.py:155) inherits selected metadata, excluding accumulated workflow state.
- `run_segment` forwards the prepared input without fetching the workflow checkpoint.

Consequently, A’s state can satisfy B’s gate while **B receives none of that state**. The retained [S5 assertions](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_gact/test_declared_workflows_s5.py:459) explicitly require B to see A’s contribution and C to see both A’s and B’s.

The narrow correction is to supply the accumulated state through the existing durable `launch_context` path when admitting a new step. Preserve that admission-time snapshot when resuming an already accepted child; do not replace it with later workflow state.

The replacement contract test should inspect the child’s actual model input, including after interrupted admission/recovery. Checking the final accumulator or gate result alone would miss this regression.

No production changes or tests were run. The external-file EOL/index clarification does not affect this finding.

---

**Source NO-GO for `f020a591`.** The correction packet addresses the main ownership problems, but four correctness gaps remain:

1. **[P2] Context recovery drops work after compaction.**
   In [conversation_projection.py:119](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_projection.py:119), a row containing a summary is replaced by that summary, then skipped. Compaction can occur midway through an assistant message, so later tool calls, results and the answer in that same row disappear during transcript fallback. Preserve the uncovered parts after the compaction checkpoint.

2. **[P2] Startup can transfer an old pause to a successor assignment.**
   [conversation_recovery.py:107](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_recovery.py:107) checks `agent_paused` without checking `agent_paused_assignment`, then binds the pause to the latest assignment. Stale metadata belonging to assignment A can therefore pause successor B after restart. Recovery must apply the same assignment identity check as the live pause logic.

3. **[P2] Deferred Stop-hook approval can bypass an expired deadline.**
   [conversation_assignments.py:224](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:224) completes the assignment and removes its timer without checking `execution_deadline`. If approval wins the lock after expiry but before cancellation is recorded, the assignment becomes successfully completed. Apply the existing deadline check at this terminal transition too.

4. **[P2] An older workflow invocation can resume a newer retry.**
   [workflows.py:494](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/workflows.py:494) consults only the latest checkpoint. After invocation A fails and retry B starts, re-entry with A’s identity returns B’s unfinished execution and can advance it. That violates C7’s “identical invocation reads history” rule. Resolve historical invocation identity before choosing the current resumable execution.

**C8 also has remaining resource-retirement scope.** Both [native_tools.py:691](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:691) and [external_tasks.py:560](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/external_tasks.py:560) require an effective terminal timestamp before releasing completed observer objects and SDK bindings. Unknown settlement intentionally has no such timestamp, so these references can remain indefinitely after observation finishes. This establishes retained resources, **not a proven running-worker leak**. Their retirement needs to preserve the durable uncertainty, admission hold and ability to re-observe.

The central changes otherwise look sound: proof precedes context restoration; plan-resolution mail precedes gate clearing; live pause/resume targets the assignment; merged workflow steps are preserved; and nonfinal backend evidence does not acknowledge collection or settle an older unknown incarnation.

These fixes belong in the existing owners—no additional coordinator or task framework is warranted. Strict restart restrictions remain intentional under unchanged R2.

Reviewed committed source only. No edits, tests, builds or services were run; reported static checks and runtime acceptance remain separate.
