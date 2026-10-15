# Astra storage-owner review

Read-only architectural review of `9f517191`; implementation acceptance is separate.

**Yes. Use `QuestionCommands` as the durable owner for turn-ending hook approvals, with `app.state.permissions` only a compatibility projection.** I would revise my earlier recommendation to persist more of the old permission row.

At `9f517191`, Questions already provide durable acceptance, immutable answers, answer/cancel arbitration, and [frozen resolution data](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/questions.py:236). Building those capabilities around the permission dictionary would create a second approval lifecycle.

| Approach | What it requires |
|---|---|
| Make turn-defer permission rows durable | Add acceptance, immutable decisions, cancellation arbitration, recovery and effect replay around the old owner. |
| Adapt turn-defer to Questions | Reuse that lifecycle; add hook-specific binding, authorization and decision effects. **Recommended.** |

This fits [R2’s ownership rules](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:54): Question commands own answer/cancel transitions; conversations own assignments; permission gates retain their safeguards. It needs no scheduler or registry.

The smallest correct adapter has these requirements:

1. **Bind the approval to the exact deferred work.** At creation, retain the original notification identity, revision/content reference, assignment and context epoch, plus the hook event. Use a stable invocation identity so replay finds the same Question. For Stop, capture the assignment then; the [current resolver selects the latest assignment when approval arrives](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/defer.py:430).

2. **Keep approval authority narrower than ordinary Question control.** The [generic answer boundary](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/question_surface.py:66) permits callers with task-control rights. An owning agent can have those rights. Hook approval therefore needs its existing authenticated grantor restrictions on **every** answer surface, including generic Question controls. An answered Question is not necessarily an approval: denial, cancellation and expiry need explicit handling.

3. **Make publication and recovery ordering safe.** Persist the binding and establish the input hold/gate before an answer can release execution. Freeze the decision before applying its effects; clear only the matching gate after those effects are confirmed. Existing [Question recovery](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/question_events.py:109) is useful infrastructure, but currently dispatches plan decisions and depends on an existing gate pointer. It does not automatically repair a crash between Question creation and gate installation. Early approval must also make later turn finalization harmless: no re-holding withdrawn, committed or revised input.

4. **Preserve the original native input.** For human/composer prompts, approving and releasing the same retained message with trusted approval metadata is the simplest candidate. It preserves its media-rendering path and avoids a text-only replacement. Question reply attachments do not automatically preserve the original prompt’s images/files. Denial must resolve the original pending input so it cannot immediately trigger the hook again.

5. **Separate control completion from model input.** Questions normally [publish an owner outcome notice](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_publication.py:26), and `question_answer` is eligible to wake the session. Blind reuse would let a Stop approval complete the assignment and then immediately start a successor. Keep control-only outcomes observable but non-waking through the existing mailbox policy. Approved Stop should call `complete_deferred` for the captured assignment; explicit Stop denial may produce feedback. Cancellation/expiry must not silently approve or manufacture a continuation.

6. **Keep legacy uncertainty explicit.** Migrate identities and retained evidence where possible. Without a verified original-input binding, preserve a visible, non-executable unresolved approval. Do not guess from matching text or the latest assignment, and do not retain the old resolver as a fallback.

The replacement should remove these **turn-defer authorities**:

- Mutable permission-row status/action as the decision store.
- Turn-defer entries in `hook_defer_pending` as a second pending lifecycle.
- `pending_defer_permission_id` as an independent execution gate.
- `resume_text` as the authoritative reconstruction of input.
- The turn-defer branch in [the old permission resolver](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/permission_gate.py:418), including its “mark resolved before effects” behavior.
- Separate turn-defer recovery decisions, replaced by replay of the Question’s frozen decision through existing recovery machinery.

Public permission IDs, cards and routes can remain thin projections/delegates. **PreToolUse enforcement, parked-call events, intercepts and permission policies stay with their existing owner.** Shared helpers in `hooks/defer.py` must therefore be assessed individually.

I endorse this architecture over extending the old dictionary. This was source review against `9f517191`; no implementation or runtime qualification was performed.
