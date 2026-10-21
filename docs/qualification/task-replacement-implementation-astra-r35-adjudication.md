# R34 combined source adjudication

Read-only adjudication in the existing Astra review chat, turn `01a13ef8-eeb1-77c3-a837-7b24269dd098`. This concerns the committed R34 tuple; subsequent R35 corrections remain unexecuted and unapproved.

**Combined verdict: the architecture is sound; two bounded source corrections remain; qualification is still pending.** Fable’s proposed changes to Stop and `wait(any)` should not be adopted—they contradict established behavior.

This adjudication covers core `47380c05`, GACT `07745d5b`, and marketplace `999fdafa`.

1. **[P2] Child-session reuse can skip unfinished initialization.**
   [SessionStore.create](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/sessions.py:411) treats an existing matching session as fully created, returning before lifecycle publication and `SessionStart`.

   If the first flush fails after inserting the in-memory row, a same-process retry can successfully persist that row and accept its assignment without ever publishing `session.created` or attempting the hook. A failure before lifecycle publication produces a similar gap.

   Fix this through the existing session/provenance recovery paths. Preserve the stable child address, reconcile known unfinished creation, and retain uncertainty when an effect might already have happened. No new transaction service or exactly-once mechanism is needed.

   The [regression](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_arc/test_child_creation_recovery.py:79) always reconstructs `SessionStore`, missing the same-process case. Add that case and a failure before the real lifecycle observer publishes; verify one child address and that known-unattempted initialization is completed.

2. **[P2] “Load more work” hides actual pagination failures.**
   [The hook](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/hooks/use-workspace-data.ts:502) calls `fetchNextPage()` without `throwOnError`, while [the component](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/components/clio/async-task-list.tsx:39) displays errors only when that promise rejects. The pinned library catches rejection and returns query error state by default. [TanStack source](https://raw.githubusercontent.com/TanStack/query/@tanstack/query-core@5.102.0/packages/query-core/src/queryObserver.ts)

   Request rejection for this action or expose the query error state through the existing component. Test the actual hook/component boundary: failed second page, visible error, retained first page, successful retry. The current mocked rejecting callback cannot catch this mismatch.

The disputed findings resolve as follows:

| Finding | Adjudication |
|---|---|
| **Eligible results or peer mail release Stop-held input** | **Intentional.** [R32 explicitly permits accepted eligible work to release that hold](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-r32-corrections.md:21). An ordinary wake hint cannot. Fable applies the separate rule for **veto/setup failures** to ordinary Stop. Preserve the implementation; strengthen coverage for task results, Question answers and authorized peer mail, including pause, retry-supersession and cancellation cases. |
| **`wait(any)` returns a member error while valid work remains pending** | **Intentional.** The [existing regression specifies exactly this contract](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_arc/test_task_replacement_contracts.py:200). Errors do not cancel other members. Clarify tool wording that “any” includes a member error; retain the explicit `pending` list. |
| **Workflow results lose some observation metadata** | A limitation worth documenting, but no present unauthorized disclosure is established: these workflow children have own-tree access. It does not justify expanding the architecture. |
| **Work/Observability shows active tasks** | Already stated in the [R34 correction map](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-r34-corrections.md:15). Verify that historical work remains accessible through Runs after reload and make the UI scope clear. |
| **Full-history indexes and authorization-lock contention** | Measurement obligations for F03, not demonstrated defects requiring another cache, registry or coordinator. |

The important architectural improvement remains intact: one task representation, one Core writer, explicit execution owners, and one recipient-input acknowledgement boundary. The remaining corrections fit those owners.

The updated [construction receipt](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/qualification/task-replacement-r34-construction-checks.json) records final scoped Linux Mypy and package-declared Core/Web TypeScript checks as passed on the committed candidate; both reports’ earlier type-check caveats are superseded. **R34 behavioral tests, migration, F03, exact-head CI and the live acceptance matrix remain pending.** Earlier R33 passes do not qualify this candidate.

This was read-only source adjudication. I made no edits and ran no tests, services or qualification.
