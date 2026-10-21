# Independent Astra correction-plan review R19

Source-only review; no runtime acceptance.

**R19 is sound for C1–C7, with the deadline clarification below. C8 needs an explicit distinction between inspection, settlement and permission to continue.** The current defects do not justify treating unknown cleanup as confirmed.

Reviewed against production `19319a3b`, R17 and the actual Claude R18 report. No edits, tests or services.

**C8: the smallest recovery path under unchanged R2**

A retired parent **can remain available for authenticated human inspection through the existing status, result and control routes**, while its cancellation/admission hold remains intact. Worker retirement does not establish descendant settlement.

The existing conversation owner should:

1. Finish retiring the parent worker and requesting cancellation of the captured subtree.
2. Record unresolved members and one attention episode. Preserve the cancellation hold and leave the assignment nonterminal.
3. Return from cancellation processing once only genuinely unknown settlement remains. Keep actual ongoing cleanup owned; do not abandon a running retirement operation.
4. Re-evaluate settlement through existing owner observations, explicit re-observation and startup recovery. Later proof may finalize cancellation, but must never automatically launch a successor.

The current `_cancel_subtree` instead remains suspended at `changed.wait()` after reporting uncertainty. Replace that indefinite control coroutine with bounded owner processing and existing observation callbacks; retain the captured membership in Core. This requires no new coordinator. [Current cancellation loop](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:490)

**Ordinary model continuation or restart while necessary cancellation settlement remains unknown requires an R2 amendment.** Merely allowing human mailbox items through `eligible()` would silently bypass the cancellation contract. R2 expressly requires known necessary settlement and forbids restarting through unsettled cancellation. [R2 contract](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:106)

Consequently, “the human accepts the uncertainty” cannot set `settlement=confirmed`. If continued agent work despite unresolved external work is required, define a narrow, authenticated continuation exception separately: record the exact unresolved handles and decision, preserve their unknown status and original cancellation intent, and require a deliberate continuation request. R19 should not present that exception as already authorized by R2.

There is an unavoidable limit: **when an external owner cannot supply cleanup evidence, unchanged R2 permits inspection but may permanently prohibit restarting that assignment.** Removing the waiting coroutine improves resource ownership; it does not solve that product-policy restriction.

**C8: persistent native redelivery**

Recording backend completion separately from unresolved physical settlement is sufficient—and already fits `raw_status`, `backend_observation`, `settlement` and incarnation receipts.

A fresh completed attempt must:

- Retain its validated output and its own cleanup receipt.
- Leave an earlier unknown incarnation unchanged.
- Expose the backend output as **nonfinal evidence**, with `pending=true`, `settlement=unknown` and no final collection acknowledgement.
- Keep the eventual final notification distinct from the existing attention episode.

Currently `_settle()` returns on an unknown attempt before validating/exposing the retained result, while `TaskOperations.result()` returns before reading any output for nonterminal tasks. Those are the narrow places to correct. [Settlement](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_task_settlement.py:83), [result reads](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:162)

Finishing the old incarnation requires **evidence tied to its actual resources and identity**: its cleanup receipt, or verified owner-specific recovery evidence covering the outstanding effects. A new attempt finishing, a backend lease expiring, a PID disappearing or a human saying “continue” is insufficient.

There is already a useful implementation precedent: storage continuation records evidence for specific previous incarnations only after checking provider cleanup and absence of earlier local publication. Reuse that domain-specific approach where available; do not generalize it into a universal settlement mechanism. [Existing storage evidence](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_storage.py:209)

Also distinguish **uncertain work** from **a cancelled assignment**. An active assignment without a cancellation hold may deliberately inspect and retry/revise work under the existing recovery contract, creating a new linked handle. Unknown cleanup must not become a universal prohibition on all deliberate retries.

**C6: approve the conversation-owned deadline timer**

The conversation owner owns the assignment and subtree cancellation, so it is the correct location. I found no existing assignment-deadline mechanism that would make this simpler.

Keep these conditions explicit:

- Persist the deadline once before admission; define its starting point.
- Parent Stop, re-entry, pause and service recovery never renew it.
- At startup, enforce an expired deadline before admitting inference.
- The callback targets the exact assignment and calls existing cancellation; stale callbacks cannot affect successors.
- Expiry closes admission and requests cancellation. **Physical cleanup may finish later or remain uncertain**; the deadline cannot promise instantaneous termination.
- Retire the timer independently from the cleanup work it initiated.

Remove the workflow’s timeout argument from shared `wait`, as proposed. Preserve a typed “execution deadline exceeded” reason so workflow callers can distinguish it from ordinary cancellation.

C1–C5 and C7 address the reviewed losses without restoring deleted owners. For C2, retain the explicit “clear only this Question’s gate” check during startup repair as well as live resolution. The remaining approval condition is to write C8’s inspection/continuation boundary into the packet before implementing it.

---

**The confirmation rule is correct; the fallback needs tightening.** `arc.op` precedes the context write, so it cannot prove delivery. [Write ordering](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/arc/working_set_fold.py:356)

Use this boundary:

- **Confirmed input:** retain `recipient_input` only when it matches independently confirmed canonical Core evidence. Match the complete identity and payload—session/scope, assignment/iteration, content references, rendered content and boundary—not merely notification IDs. Establish that proof **before restoration**, so the restored segment cannot become its own confirmation. Preparation events and rebuildable indexes are not independent proof.

- **Unconfirmed input:** preserve it as historical evidence, but **do not automatically convert its rendered messages into ordinary live user context**, even with an uncertainty label. Removing notification IDs bypasses the existing exclusion of uncommitted input. It could expose withdrawn feedback or content whose authorization changed, then deliver it again through the still-pending mailbox. [Current context filter](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/context_reader.py:156)

- **Recovery behavior:** leave accepted mail pending and let the existing mailbox path recheck withdrawal, authorization and admission before committing it. Add a concise recovery notice that prepared input was found but delivery is unconfirmed. Keep its contents available for authorized inspection; do not treat them as newly admitted instructions. [Existing commit checks](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:187)

Preserving original IDs, correlations and tombstones for ordinary historical segments is appropriate. Restore only an **absent** exact scope; an intentionally cleared or fully tombstoned scope must not be resurrected. Missing proof and failed/unavailable proof reads must remain distinguishable.

Suggested C1 wording:

> Restore validated same-session context evidence without manufacturing delivery acknowledgements. Preserve recipient-input records only against independently confirmed canonical input evidence. Unconfirmed preparation remains inspectable historical evidence and pending mail; it does not become actionable model input through context restoration. Normal mailbox admission and recipient-input commitment govern any later delivery.

That preserves the existing recovery and delivery owners. No tests or services were run.
