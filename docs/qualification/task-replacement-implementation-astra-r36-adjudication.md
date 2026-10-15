# R35 combined source adjudication

Read-only review of core 182cde82 / GACT 41660185 / marketplace 999fdafa. Thread `01a131d2-519c-7ec2-b9a5-5a7ab0efe495`, turn `01a13f32-3d7b-7c32-95d1-8cd8ade599be`.

**Combined verdict: architecture supported; source readiness still blocked by initialization lock scope and timed-workflow recovery. Qualification remains pending.** Fable’s input-redelivery claim is not supported by the current recording path.

This applies to core `182cde82`, GACT `41660185`, marketplace `999fdafa`.

1. **[P2] Child initialization holds the global task lock across hook execution.**
   Confirmed. [spawn.create](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:425) holds `TaskHistory.serialized(writing=True)` through session creation, lifecycle publication, session-file flushes and [SessionStart dispatch](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/sessions.py:477). The dispatcher synchronously waits for configured hook processes.

   A slow hook blocks unrelated task reads, mail acceptance, Question answers and controls. A hook calling back into those APIs can wait on the lock held by its own caller until timeout. This is a concrete liveness defect, beyond an unmeasured performance concern.

   **Bounded correction:** keep identity/admission checks and confirmed task/mail writes serialized, but perform session initialization outside that global critical section. SessionStore must retain one initializer per trusted creation identity. Recheck parent cancellation, authorization and assignment state before accepting the child. Merely removing the outer lock would introduce races.

2. **[P2] Timed workflow retries change their immutable creation request.**
   The previous finding stands. [Workflow launch](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/workflows.py:689) recalculates the absolute deadline while retaining the step invocation identity. That deadline participates in the creation digest. After a pre-assignment failure leaves a reusable session, continuation rejects it as different work.

   **Bounded correction:** persist the prepared deadline in the existing workflow checkpoint before child creation and reuse it during recovery. Preserve the digest check and original budget.

3. **[P3] Reuse overwrites a human-editable approval setting.**
   [The approval-profile branch](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:487) reapplies `approval_mode="ask"` even when reusing a child. This contradicts the stated preservation of human edits. The server-owned profile still governs permission decisions, so this is not evidence of a permission bypass.

   Apply initial policy during original session initialization; validate the immutable profile on reuse without resetting mutable settings. Include this in the initialization correction.

**The durable-input finding needs a regression, not Fable’s proposed assertion.** With an input notification identity, [user_message](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:377) saves the head in memory and returns before writing a user segment. Later, [commit_input](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:467) creates rendered references only for the final `staged.items`. The model request reads that recorded context.

Consequently, if budgeting excludes the trigger, it is neither rendered nor acknowledged; it remains pending. The claimed “already delivered but unacknowledged” sequence does not follow. Test the actual boundary: an earlier item becomes eligible after admission, consumes the batch budget, and the trigger remains absent from model context and pending across recovery, then is delivered once. An assertion forcing trigger inclusion could instead break accepted ordering or fail an otherwise valid turn.

The remaining findings classify as follows:

| Finding | Adjudication and bounded action |
|---|---|
| Lifecycle confirmation depends on an off-loop caller | Current trusted production calls use `asyncio.to_thread`; no current failing route was established. Make that requirement explicit while correcting initialization—reject unsupported loop-thread use before effects, or await actual confirmation. Never mark a scheduled write confirmed. |
| `started` hook receipt cannot automatically resume | Intentional uncertainty, already documented in the R35 map. Preserve non-replay. Clarify the existing error/evidence path and available recovery choices; this does not justify a new hook-recovery service or automatic resubmission. |
| Repeated waits return existing uncertainty | Required by R2’s actionable-uncertainty contract. Do not change this to “only uncertainty arising after this wait.” Clarify prompts to distinguish ordinary pending work from uncertainty requiring inspection. |
| Pattern observation returns an unavailable-member outcome | An independent member outcome, not cancellation of valid peers. Clarify continuation with the remaining valid handles; no new observation lifecycle is warranted. |
| `recovery_input` scans all committed inputs during child creation | The scan is confirmed; its cost is unmeasured. Include it and the additional full-session flushes in F03. Any correction belongs in existing Core input projections, not another cache or persistence framework. |

The replacement map should therefore stay small:

- **SessionStore/Conversations/provenance:** initialization ownership, lock scope, explicit confirmation and preservation of settings. Test concurrent same-identity calls, cancellation during initialization, unrelated Question/control progress, and existing fault cases.
- **Workflow checkpoint owner:** stable prepared deadlines. Test timed-step recovery before assignment acceptance with the same session and deadline.
- **Recorder/mailbox tests:** the admission-to-commit budget race described above.
- **Existing guidance:** distinguish pending, unavailable and uncertain outcomes without changing wait semantics.

The pagination correction remains sound in source. The new tests use production owners and real Core/QueryClient boundaries, with appropriate fault-injection doubles; they are not live hook, provider or product acceptance.

Final scoped Linux Mypy and declared Core/Web TypeScript are now reported passed on this tuple, superseding the reports’ pending-type caveats. Behavioral execution, legacy-test migration, F03, exact-head CI and Q1–Q9/R1–R6 remain outstanding.

Read-only adjudication only: no edits, tests, services or qualification performed.
