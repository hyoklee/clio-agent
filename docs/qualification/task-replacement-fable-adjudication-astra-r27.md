# Astra adjudication of Fable R26

**Fable identifies two defects worth fixing, but its `any`-wait recommendation would change preserved behavior.** The architecture remains defensible; source approval is still NO-GO.

1. **Confirmed: validation failure is incorrectly deferred as a recording failure.**  
   In [conversation cancellation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:339), `require_execution_owner()` can reject a nonlocal historical assignment before any write occurs. The broad exception handler nevertheless adds a control hold and queues the same permanently invalid request. For an active assignment it also reports cancellation requested with recording unconfirmed. Recovery retries indefinitely, and shutdown drain cannot finish. Validate ownership before entering the recording-recovery path; only retain genuinely recoverable operations. This is a blocking defect.

2. **Confirmed, but narrower: conversation uncertainty can remain stale after evidence improves.**  
   Keeping attention while assignment history is unavailable is correct. The clearer defect occurs during subtree cancellation: after an uncertain descendant reconnects and becomes known-but-still-cleaning-up, [the cancellation watcher](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:599) has no branch restoring the parent’s known pending state. Its old uncertainty and attention remain, so [shared waits return immediately](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:291). R2 expressly requires continued waiting for known cleanup. Clear the resolved episode when the owner has evidence—not merely when execution resumes.

3. **Not a demonstrated defect: `any` waits returning a per-member error.**  
   This behavior predates the replacement. Baseline `5475042f`, `src/clio_agent/gact/task_controls.py:290`, explicitly returned when `return_when == "any" and (settled or errors)`. The replacement preserves that behavior, reports the unavailable member, and leaves valid pending work running. R2 requires preservation and independent outcomes; it does not require ignoring errors until another member settles. Document and test this contract rather than silently changing it.

The broader recommendations need qualification:

- **Do not restrict recovery to recording failures alone.** [R2 explicitly includes original-identity reattachment](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:92). The problem is admitting permanent validation failures and allowing RPCs to block unrelated repairs—not the presence of multiple owners’ recovery entries.
- **The provider-continuation custody check is validation, not an execution engine.** [Its special case](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/arc/task_types.py:203) enforces the continuation exception permitted by R2. It starts no work and makes no scheduling decision.
- **The subtree watcher implements required conversation-owner responsibilities.** Its size warrants readability work, but event-driven cancellation and late-settlement observation do not establish a redundant generic supervisor.
- **Replay and ARC-private access are real maintenance concerns, not automatic architecture violations.** Replay is outside normal hot reads; R2 permits reconstruction and requires measurement before optimization. The unused persisted-index writes remain a separate concern from my previous review.
- **GACT’s registry terminology is stale documentation.** Compatibility fields and defaults are permitted; the old wording does not establish a surviving registry authority.

The R19/R21/R23/R26 correction documents **are committed** at this snapshot. Their absence from Fable’s package is another packaging limitation. Its “every behavioral gate remains unexecuted” wording is also too broad: the ledger records earlier component checks, while the current correction packet and integrated acceptance remain unqualified.

My earlier collection-revocation, cancellation-RPC, and REST-pagination findings remain outstanding on this frozen candidate. This adjudication involved source reads only; no edits, tests, or services.
