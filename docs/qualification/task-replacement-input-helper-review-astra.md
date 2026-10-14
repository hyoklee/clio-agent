**Both proposals are compatible with R2, with the refinements below. Neither requires another execution authority.** This is an architecture decision; it does not clear the outstanding implementation or acceptance gates.

**Use an ordinary helper assignment through the conversation engine.** That follows R2’s ownership split: Conversations owns model execution, Question commands own answer/cancel arbitration, and the SDK adapter handles protocol input. [R2 ownership](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:56).

Keep the implementation within these boundaries:

1. **Bind the helper durably before admitting it.** Associate the exact Question/request identity, immutable payload/schema and helper assignment handle. Re-entry and recovery reuse that association and the existing assignment/input recovery path. They must not create another helper merely because the callback reconnected. This does not require exactly-once model execution or a new registry.

2. **Use the existing elicitation callback for both stages.** Before task acceptance, there is no `ToolTask.result()` observer yet: bind to the confirmed submission and actual request identity. After acceptance, retain the full backend/auth/session/task/input-key binding. Keep normal SDK pre-task re-entry and the single post-acceptance result driver. [R2 SDK boundary](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:68).

3. **Wait for either the Question to resolve or the helper to finish.** Waiting only on the helper would strand an already supplied human answer behind slow inference. Shared `wait(..., return_when="any")` can handle these two fixed handles. Helper completion proposes a validated, attributed answer through Question commands; a human answer, cancellation or expiry that already won remains authoritative. Helper failure or uncertainty follows the retained fallback policy without inventing an answer or launching an automatic replacement.

4. **Preserve execution and permission boundaries.** Give the helper its own session worker, the trusted answering model, bounded authorized context references and an enforced empty tool allowlist. Releasing the parent’s inference permit is necessary; the helper must also avoid any provider/session lock still held by the parent’s RPC. Parent cancellation includes the helper through existing ownership. URL consent and permission decisions remain on their existing trusted paths.

5. **An SDK read is not parent-model delivery.** The callback may read the helper result through shared operations, but must not manufacture a parent recipient-input commit or acknowledge its mailbox notices. Persist the winning typed Question answer and canonical SDK response before returning it. The existing Question owner already supplies answer/cancel arbitration. [Question commands](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/questions.py:120).

**Summary-only automatic notices for external MCP form answers are also compatible.** Implement this as content selection within the common publication/input path, preserving the full typed answer in Core and authorized explicit reads.

Two details matter:

- Say **“Answer recorded for …”** until backend receipt is confirmed. “Input supplied” can imply that the server received or acted on it. Decline, cancellation and delivery uncertainty need their actual meanings.
- Apply the same treatment to the linked helper’s automatic completion notice. Otherwise its full structured answer enters the parent context through ordinary Subagent completion, defeating the proposed reduction. Currently the common publisher uses `current.result` directly. [Publication](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_publication.py:24).

The recipient-input record should describe the summary actually delivered, with references to the retained answer. Ordinary `ask_user` answers continue through normal answer injection.

The narrower design is therefore **one SDK callback, one fixed Question, one ordinary helper assignment when policy permits, and the existing shared wait/answer/publication paths**. Remove the old inline LM call, dispatch task set and alternate answer-turn workers.

Read-only adjudication only; no edits, tests, models or services launched.
