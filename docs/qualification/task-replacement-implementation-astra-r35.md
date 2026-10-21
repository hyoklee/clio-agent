# Independent Astra review R35

Read-only review of core 182cde82 / GACT 41660185 / marketplace 999fdafa. Thread `01a131d2-519c-7ec2-b9a5-5a7ab0efe495`, turn `01a13f1c-c48d-7123-9237-ff417d8f96bc`.

**Architecture: GO in principle. Source: NO-GO on one recovery defect. Qualification: pending.**

Reviewed core `182cde82df09b60c9b5dc13b0f3d5fdb3e447fb5`, GACT `416601856a1e828f658fd59fe6bc5bc4f1129f05`, and marketplace `999fdafa9d0f1214e3f9f4f98a6d4d4a8f8f3751`.

**[P2] Timed workflow steps cannot reliably resume after pre-assignment creation failure.**

[run_declared_workflow](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/workflows.py:681) reuses the workflow execution and step invocation identity, but computes a fresh absolute `execution_deadline` on each launch attempt. [Conversations.spawn](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:460) includes that deadline in the immutable creation digest.

The failure sequence is:

1. A step with `timeout_s` creates its child session, then fails before recording the assignment.
2. Recovery retains that session with the original creation digest.
3. A later workflow call resumes the unfinished execution. It uses the same step identity but computes a different deadline.
4. [SessionStore.create](/C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/sessions.py:419) rejects reuse as “different work,” preventing the intended continuation.

Persist the prepared deadline in the existing workflow checkpoint before child creation and reuse it during reconciliation. Keep the digest check intact. Add a regression through `run_declared_workflow` with a timed step and a pre-assignment fault, covering same-process and reconstructed-store recovery. Verify the original session, step identity and deadline survive without duplicate launch.

This is a source-established failure sequence; I did not execute it.

The two previous R34 defects are addressed in source:

- Child initialization now distinguishes pending, completed and uncertain hook dispatch, checks existing Core creation evidence, and resumes known-unfinished initialization. The new tests exercise same-process recovery, reconstructed stores, publication failures and visible hook effects.
- Pagination now requests `throwOnError` through the existing observability owner. Its regression uses the production hook and continuation component, checking a visible second-page failure, retained rows and successful retry.

The broader design remains consistent with R2:

- **Stable sessions and finite assignments:** yield and continuation preserve active assignments; successors have distinct handles; restart checks settlement before creating one.
- **Intersession messaging:** shared mailbox acceptance and input commitment retain attribution and authorization checks. Exact historical grants do not automatically authorize successors.
- **Observation and waits:** queries and observations do not acknowledge delivery; collection uses the recipient-input boundary. The established member-error behavior of `wait(any)` is preserved and now described explicitly.
- **Questions:** `ask_user` returns a durable handle; answer/cancel transitions belong to `QuestionCommands`; shared waits collect outcomes. Stopping a waiter leaves the Question open.
- **Removal and maintainability:** I found no restored retired registry or task driver in production source. The remaining correction fits the existing workflow checkpoint owner.

Regression quality has improved, but the child-creation tests omit timed workflow callers. Existing workflow checkpoint tests establish retry/provenance behavior within one workflow history; they do not establish communication between **two independent workflow executions**. The message-alias smoke test likewise does not close Q5’s replies, grants, revocation, subscriptions and denied-control matrix.

The construction receipt reports scoped lint/types/guards passed, with final tuple types still pending at inspection. R34/R35 behavior remains unexecuted; legacy-test migration, F03, exact-head CI and Q1–Q9/R1–R6 remain outstanding. F03 should include the additional full-session flushes introduced by initialization receipts.

No edits, tests, services or qualification were performed. Protected references and manual-only roots were untouched.
