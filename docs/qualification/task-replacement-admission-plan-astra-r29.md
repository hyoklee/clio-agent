# Astra review of the bounded admission correction

**The proposal fits R2 and uses the right owners.** I would approve it with the following explicit safeguards; adding the original notification ID alone is insufficient.

1. **Finalization must recheck the exact attempted input.**
   Under the existing writer lock, check its current pending state, revision/content identity, acknowledgement, and withdrawal. Hold only the still-pending input that this attempt actually processed. An early approval may already have withdrawn it; that must make the later hold a no-op. [update_mail](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:549) already rejects edits to withdrawn or committed input, so blindly applying the old trigger would turn successful approval into a finalization error. Preserve existing cancellation and context-epoch guards.

2. **Make the approval decision and recovery binding durable before reporting resolution.**
   At `5eab9ef8`, `app.state.permissions` is an in-memory dictionary. [The durable defer mirror](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/defer.py:374) stores only kind, event, and timestamp—not the original input or resume payload. Moreover, [resolve_permission](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/permission_gate.py:418) marks the row resolved **before** applying the continuation; subsequent calls then return without retrying it.

   Extend the existing owner’s durable representation with the exact input/content reference, accepted decision, and stable continuation identity. Validate before accepting the decision. Repeated resolution must finish the same accepted decision; conflicting decisions must not replace it.

   The proposed ordering is sound:

   **Accept continuation mail → withdraw original → clear the matching gate → signal.**

   Here “accept” means durable mailbox acceptance, **not** a premature recipient-input acknowledgement. Keep the gate until the preceding writes are confirmed. Serialization orders these operations but does not make their separate writes crash-atomic.

3. **Derive retry supersession from trusted provenance.**
   Keep the existing authenticated retry owner and its context-reference authorization. However, do not use client-overridable metadata as authority to withdraw another input. [Retry staging currently spreads `req.metadata` last](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/sessions.py:813), allowing overrides of fields such as `retry_source_user_message_id`. Derive the exact Core notification server-side and protect that binding. The existing “nearest preceding user message” helper can select retry content; it is not sufficient proof for superseding a held notification.

4. **Preserving references must include the rendering path.**
   The existing approval continuation is text-only. Merely putting an original-content reference into its JSON will not restore native images/files. Route the retained message through the existing [typed human-input renderer](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/messaging.py:567), preserving attribution, reference authorization, native media, and indivisible human-input budgeting. Keep the skip-hook marker host-controlled and bound to that approval.

5. **Legacy approvals need an explicit unresolved outcome.**
   Recover an original identity only from verified retained correlation. Do not guess from matching text, the latest assignment, or the oldest pending message. If no exact binding exists, retain the gate and expose an actionable legacy-resolution failure; do not mark the approval resolved, withdraw unrelated input, or clear the gate and accidentally re-admit the rejected prompt. Apply this rule to `UserPromptSubmit`; Stop approvals have different semantics.

There is one optional simplification: for a human/composer prompt, approval could use existing `update_mail` to amend and release that same retained input with trusted approval metadata. That preserves its kind and media path and avoids creating a replacement then withdrawing the original. It still requires the revision check, durable decision, and matching-gate release above. Explicit retry can retain your replacement sequence.

No new scheduler, general reconciliation framework, or session-error polling is needed. This was a read-only proposal review against `5eab9ef8`; no edits, tests, or services were run.
