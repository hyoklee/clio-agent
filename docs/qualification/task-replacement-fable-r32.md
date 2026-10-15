# Independent Claude Code Fable review R32

Core a529569d; GACT 458313c. Committed source, acceptance ledger and correction maps; neutral two-paragraph brief; read-only source review.

Review complete. Here is the independent read-only assessment of core a529569d, GACT 458313c3 and marketplace 9257bba5 against the plan and the acceptance ledger.

## Verdicts

**Architecture and ownership: conforms.** The replacement keeps one passive Core writer, the conversation engine as the sole assignment owner, QuestionCommands as the sole answer/cancel owner, and the recipient-input commit as the only acknowledgement. I found no restored registry, scheduler, driver loop or relay owner. The R32 corrections are present: retirement reconciliation is bound before the admitted coroutine can be discarded in `turn_runner.py:248-257` and runs once after worker exit in `conversation_recovery.py:362-417`, fresh assignments start `queued`, subscriber publication resolves the recipient's own principal, cursor validation precedes subscription mutation, and Runs pages the shared cross-session query.

**Source: not approvable yet.** No blocking ownership violation, but the defects and regression gaps below should be corrected before the freeze.

**Qualification: blocked.** Only static checks have run. The constructed R32 batch is unexecuted, and the ledger's own Q1–Q9, R1–R6, F03, CI and legacy-test rows are untouched. Nothing in this snapshot qualifies runtime behavior. The three hash-tagged human reference documents are absent from the snapshot, so I could not review the messaging design against them.

## Source findings

- **Hot reads still scan lifetime history (F03).** A query filtered by `kind` alone seeds from the global kind index and walks each candidate's ancestry in `task_operations.py:98-112`, so a tree-scoped query costs every task of that kind across all sessions. Segment finish loads the whole lifetime tree each time in `conversation_assignments.py:201-205`, and cancellation membership does the same in `conversation_controls.py:250-261`. The R32 admission fix did not reach these paths.
- **Writer lock held across Core I/O on reads.** Observation pages read up to forty chunks under the global lock in `task_observations.py:58-115`, and every wait wake re-reads all settled results under it in `task_operations.py:276-304`. One slow observe stalls writes for every session.
- **Stale explicit collection fails the whole model input.** Commit raises on any withdrawn collected notice in `session_mail.py:274-292`. Unsubscribing withdraws the subscriber's own notices in `task_operations.py:473-480`, so an observe with `notify=false` between a wait and the next iteration makes that iteration fail instead of dropping the member.
- **Admission exceptions leave input silently stranded.** A malformed queued item raises inside admission in `conversations.py:300-301`. The pump logs and returns in `turn_runner.py:131-135` with no hold recorded and no re-signal. The design says veto and setup errors hold the exact input.
- **Promotion mints assignments eagerly.** Composer promotion creates the assignment before admission in `routes/mailbox.py:108-112`. A later edit or withdrawal leaves an active queued assignment whose description is the withdrawn text, and the next unrelated input reuses it.
- **Question idempotency is brittle.** Creation compares the full definition including mutable metadata and resolution in `questions.py:77-86`. An annotated or frozen Question makes a retried identical call fail as reused content.
- **Dead workflow branch.** The step wait is unbounded, so the `timed_out` stall branch in `workflows.py:718-732` is unreachable. Deadlines are detected later through cancellation timestamps.
- **A read-declared tool writes.** Result collection publishes notices inside `get_task_result` in `task_declarations.py:67-71`. The R32 map asks to keep this, but it contradicts the tool's `read_only` declaration and belongs in the commit path.
- **GACT cache key mismatch.** Cancellation invalidates the `runs` key in `use-task-cancellation.ts:18` while the Runs page queries under `tasks` in `runs-page.tsx:305`.
- **Marketplace.** The `cluster-operator` pack still sits at top level with an expert granting twelve relay tools in `cluster-operator/experts/operator.md:24-39`. Its README calls it historical, but it is not under `old/`. The appl-core evaluator still keys on the legacy wait alias, and the marketplace CI installs clio-agent from `develop` rather than the frozen tuple.

## Regression coverage for the four focus areas

- **Stable sessions and finite assignments:** well covered. Early, busy and final-write Stop, buffered feedback order, trusted retry during unwind, exact cancellation after retirement, pause-independent gate cleanup, applied-completion repair, deadline cancellation and uncertain subtree settlement are all constructed against real Core.
- **Intersession and distinct-workflow messaging:** gap. No test exercises the peer message path at all. Sender-right recheck at staging, `reply_to` validation, addressing a terminal handle to its stable session, invocation idempotency and the pending-only cap through the tool are untested. Only writer-level cap tests exist in `test_task_history.py:139-153`. Two declared workflow executions with retry and checkpoint repair are covered.
- **Observation and waits:** covered. Alias wakes, expired mixed waits, revocation waking a peer wait, uncertain members, invalid cursors, output pages, pattern search and subscriber principal are tested. The `any` contract treating error outcomes as settled is asserted as intentional.
- **Asynchronous Questions through shared controls:** covered at component level. Immediate post, waiter cancellation leaving the Question open, answer and cancel arbitration, native answer media surviving interrupted collection, resolution freezing and plan-gate repair are tested. No test exercises `restart` or human `intervene`, so attributed parent notices and uncertain-restart refusal remain unverified.

Nothing above is a live-behavior claim. Fresh execution of the batch and the full Q and R matrix remain the gates the ledger records as outstanding.
