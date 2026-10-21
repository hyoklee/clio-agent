**I confirm both findings, with an important distinction in the first.** Against committed core `35a2aa0` / GACT `41660185` / marketplace `999fdafa`, architecture remains supported; source readiness remains **NO-GO**.

**1. Startup cancellation exposes a defect; uncertain hook effects are not themselves a defect.**

[SessionStore](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/sessions.py:519) persists `started` before dispatch. The [dispatcher](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/dispatcher.py:140) can then raise `HookCancelled` before invoking the first adapter. The session remains `started`, and every later initialization rejects it.

There are two separate cases:

- **Known unattempted cancellation:** treating this as permanently uncertain is incorrect. The dispatcher can establish that no SessionStart invocation occurred.
- **An invocation started or its receipt was lost:** refusing automatic replay is correct. Killing its process does not undo or establish its external effects.

However, making uncertain **hook effects** permanently prohibit all future **session execution** is too strong. SessionStart is explicitly an [observation event, not a permission gate](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/events.py:116). R2 preserves the stable session across pause/resume and linked restart.

Fable’s “abandon and respawn” option therefore cannot be the sole correction without weakening that contract. A new mandatory human-acknowledgement workflow is also unnecessary for an observation hook.

The bounded correction is:

| Existing owner | Correction |
|---|---|
| HookDispatcher | Report whether cancellation occurred before **any** invocation in the dispatch. Cancellation before the second hook must not erase the first hook’s effects. |
| SessionStore | Restore `pending` only with positive evidence that dispatch was unattempted. Otherwise retain an interrupted/unconfirmed outcome and prohibit replay; do not manufacture a completed receipt. |
| TurnRunner and Conversations | Preserve physical retirement and existing continuation rules. After necessary settlement is known, allow continuation without repeating the observation hooks, carrying startup uncertainty into retained Core context. Pause still requires resume; accepted eligible work can release Stop; restart creates a linked assignment. |
| Existing control/publication paths | Expose the interruption and retained evidence. Resume/restart must neither imply that effects were absent nor bypass uncertain physical settlement. |

Required regressions should cover cancellation between the `started` write and first invocation; cancellation after a visible effect; cancellation between two hooks; pause/resume retaining the assignment; and restart retaining the session while linking a successor. Assert no replay, truthful uncertainty, and no model execution before required retirement.

**2. Target discovery under the global writer is a confirmed lock-scope defect.**

[Spawn holds the TaskHistory writer](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:425) while [create_child resolves the target](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_runtime.py:148). Task reads use the same lock. Consequently, slow discovery blocks unrelated queries, Questions and controls.

One correction to Fable’s description: discovery is **not entirely pure**. It can [recover installation revisions and bootstrap registry files](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agent_blueprints.py:179).

Keep the existing owners and split preparation from acceptance:

1. Perform a short authorized identity/parent check.
2. Resolve and validate the target off-loop, outside the task writer.
3. Re-enter the writer and recheck caller rights, parent identity/admission, evidence, depth and immutable invocation identity before creating the child and recording assignment/mail.
4. Preserve accepted-identity reuse; rediscovery must not retarget or invalidate already accepted work.

Add a held-discovery regression proving unrelated query/Question/control progress, plus parent cancellation or configuration change during preparation and simultaneous identical submissions. The hook-delay test does not establish this boundary.

**The remaining observations have different status.**

- **F03:** The global input scan and whole-session-file flushes are confirmed costs, but their latency and scaling impact remain unmeasured. Keep them explicit qualification obligations; they do not yet justify a cache, new store or recovery coordinator.
- **Stale docstrings:** Confirmed documentation defects. Update references to removed registries, spawn/wait APIs and obsolete store wiring.
- **Cohesion:** A legitimate maintainability concern, not another demonstrated runtime defect. Passing the size cap does not prove good decomposition, but another broad repartition would distract from these bounded corrections.

The chunk-reader correction remains a separate uncommitted, unexecuted change. This adjudication does not qualify it or the new regressions. I made no edits and ran no tests, services or qualification tooling.
