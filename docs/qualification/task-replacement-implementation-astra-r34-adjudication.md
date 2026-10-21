# Astra adjudication of Fable R33 findings

Read-only turn `01a13eb3-d01a-79a0-9678-b92db507f924`, against the frozen R33 production source. This is not review or acceptance of uncommitted R34 corrections.

**Architecture remains GO in principle; source remains NO-GO.** Fable adds three concrete runtime corrections and one prompt correction. Its timeout and locking findings do not justify expanding the architecture.

Reviewed against frozen core `24e7dfbb`, GACT `75495899`, marketplace `c17dcc6`.

1. **Immediate access denial — confirmed, P2.**
   [StepRecorder.step_done](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:620) lets `TaskAccessDenied` escape. It becomes a conversation error and, for an ordinary ungated assignment, [terminal failure](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:290). This affects query/observe disclosures as well as collection.

   Catch **only that typed denial** at the immediate recording boundary, retain the protected observation behind its existing placeholder, and continue recording other results. Persistence and malformed-record errors must still propagate. The current regression catches the exception itself and manually commits subsequent feedback; it does not prove the real assignment survives. Add that assertion through the conversation path.

2. **Compatibility projection reads — confirmed, P2, but narrow the wording.**
   The [compatibility routes](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/tasks.py:242) request 10,000 rows and discard continuation. Those queries are bounded, potentially examining 40,000 candidates; they are not literally unbounded.

   There is also a correctness problem: session Questions filter status **after** taking that page. With 10,000 older answered Questions followed by a pending one, a pending-only request can omit the pending Question entirely. The global Questions endpoint separately materializes all matching handles and may traverse the complete historical descendant tree.

   Correct these through existing ordered/active indexes and pagination, preserving compatibility response fields and updating consumers that require continuation. Do not silently truncate history or introduce another projection owner.

3. **Orphan child session — confirmed, P3.**
   [Spawn creates the child session before recording its assignment](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:459). If the subsequent Core write fails before a task observation exists, retry finds no assignment and creates another randomly identified session.

   This establishes abandoned session rows, **not duplicate model execution**: delegation mail has not yet been accepted. Make child creation reusable for the same spawn identity within the existing session/conversation owners. Cover failures before and after durable task observation; do not compensate by deleting a potentially committed session after an uncertain write.

4. **Marketplace Question wording — confirmed correction, P3.**
   The shipped [task-lifecycle guidance](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/clio-agent-marketplace/factorio-flat/skills/coordinate-scientific-work/references/task-lifecycle.md:19) incorrectly promises that unanswered or declined Questions fail the child assignment.

   State that `ask_user` creates a separate Question; the child can continue independent work or yield, and receives the Question’s outcome through shared delivery/waiting. Cancellation of that Question does not inherently fail its assignment. Fable’s replacement wording also needs care: the child does **not always yield**.

5. **Observation timeout — documentation clarification, not a behavioral blocker.**
   The implementation returns immediately without a pattern, and both the canonical description and retained design already say that **a pattern waits**. Clarify that `timeout_s` bounds pattern waiting and has no waiting effect without a pattern, including the compatibility description. Rejecting the combination or introducing general long-polling would change behavior unnecessarily.

6. **Native admission locking — advisory performance concern, not an established correctness defect.**
   Permission evaluation, snapshots and Core reads do occur under the writer lock. That deserves measured contention coverage, but source inspection does not establish deadlock or unacceptable latency. Preserve the serialized cancellation/admission check; moving work outside the lock requires a final consistency check.

   The Shell-named `_check_admission` call uses the same injected admission callback for both roots, so it is awkward coupling rather than incorrect storage authorization. Likewise, the second mailbox staging pass follows possible changes to held inputs; it is not automatically redundant. Avoid a new cache, scheduler or admission service to address these observations.

**Transient provider errors are a policy clarification.** Current ungated segment errors end the finite assignment as failed. The plan does not clearly require preserving that assignment after every provider failure. Document the intended behavior; do not convert every error to yield or add automatic retry machinery as part of these fixes.

For qualification, Fable’s missing-receipt statement describes its review package: I confirmed the cited check receipts exist in frozen Git. Its “40 retired-import modules” also conflates inventories; retain the reported 39 absent-import modules, including unrelated historical imports, and track obsolete API assertions separately. The old hard-drain test does assert a removed contract and needs migration. Duplicate ledger IDs C01–C03 are also confirmed.

The reported 11 selected passes remain component evidence. They do not close F03, test migration, exact-head CI or the live/race gates. The already accepted observe-only wait and workflow UI corrections remain required.

No edits, tests, services, cleanup or model qualification performed; protected references and manual-only roots were untouched.
