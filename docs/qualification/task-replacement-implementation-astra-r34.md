# Independent Astra review R34

Read-only review of core 47380c05 / GACT 07745d5b / marketplace 999fdafa. Review thread `01a131d2-519c-7ec2-b9a5-5a7ab0efe495`, turn `01a13eeb-bde8-7201-ac08-e9c075327a86`.

**Architecture: GO in principle. Source: NO-GO on two bounded corrections. Qualification: pending.**

Reviewed core `47380c05437f7ceb9f2f9c4a8ca1855348437661`, GACT `07745d5b63e16d1b1e46c0fdec9efda0d91ba0dc`, marketplace `999fdafa9d0f1214e3f9f4f98a6d4d4a8f8f3751`.

1. **[P2] Reusing a child session can skip unfinished creation.**
   [SessionStore.create](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/sessions.py:411) treats an existing matching row as completed creation: it flushes and returns before lifecycle publication and `SessionStart`.

   A concrete path is: the first session flush fails after inserting the in-memory row; Core recovery completes; the same-process spawn retry finds that row, flushes successfully, and accepts the assignment without ever emitting `session.created` or dispatching its start hook. A lifecycle-observer failure before publication creates a similar gap.

   The stable address fixes orphan duplication, but existence alone does not prove initialization completed. Reconcile unfinished creation through the existing session/provenance owners. Preserve uncertainty where effects might already have occurred; this does not require an exactly-once subsystem.

   The [new fault regression](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_arc/test_child_creation_recovery.py:79) always reconstructs `SessionStore`, missing the same-process flush-failure path. Its fixture also has no installed lifecycle observer. Add same-process recovery and a failure **before** real lifecycle publication, checking the retained creation evidence and known-unattempted hook.

2. **[P2] “Load more work” silently loses page errors.**
   [workPages.loadMore](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/hooks/use-workspace-data.ts:502) calls `fetchNextPage()` without `throwOnError`. [TaskPageContinuation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/components/clio/async-task-list.tsx:39) displays an error only when that promise rejects.

   The pinned TanStack Query `5.102.0` catches fetch rejection by default and resolves with query error state, so this catch block does not handle the production failure. The adapter exposes neither that error state nor an explicit rejection. [Pinned library source](https://raw.githubusercontent.com/TanStack/query/@tanstack/query-core@5.102.0/packages/query-core/src/queryObserver.ts).

   Either request rejection for this action or pass the query’s page-error state into the existing component. The regression currently mocks a rejecting `loadMore`, so it cannot detect this mismatch. Test the component with the real query hook and a failed second page, retaining loaded rows and allowing retry.

The other R34 corrections are supported by the source:

- Immediate disclosure denial catches only `TaskAccessDenied`; malformed data and persistence failures remain strict. The new conversation test checks that the **same assignment** survives and processes later feedback.
- Canonical and compatibility waits preserve read/observe requirements for terminal, uncertain and pending members.
- Question projections select pending work before pagination; compatibility clients follow continuation, including empty pages.
- Runs respects recorded predicate stalls and does not infer completion from only the launched subset.
- Marketplace guidance correctly separates Question outcomes from assignment outcomes.

The ownership design remains intact. Stable sessions retain finite assignments; restart checks settlement before creating a linked assignment. Peer mail uses the shared mailbox and authorization checks. Declared workflows use ordinary conversation children and shared controls. Questions remain asynchronous records collected through the same wait/result/input boundary. I found no restored retired registry, supervisor or separate delivery acknowledgement.

**Regression quality is materially better, with limits.** The route tests exercise real handlers and Core indexes; the conversation survival test exercises the runner, recorder and owner with a test-only model boundary. Those are useful component tests. The two gaps above need stronger boundary coverage. Existing workflow tests exercise checkpoint/retry behavior; they do not establish communication between two independent workflow executions. The peer-message alias smoke test likewise does not close Q5’s replies, revocation and distinct-session/workflow matrix.

R34 behavior remains unexecuted in the reviewed evidence. Final tuple type checks, migrated legacy tests, F03, exact-head CI and Q1–Q9/R1–R6 remain required. Earlier R33 passes do not accept this candidate.

No edits, tests, services, cleanup or product/model qualification performed. Protected references and manual-only roots were untouched.
