# Astra initial implementation review

Frozen core8fbd41308bc5b961049fe441781d48b368aebb8e; GACT3efef4afffb235bb2ee1873358591478ce63895c; marketplace3299065f3ee7f827f734d311d39b15bf7460ab42. Source review only; no tests or services run by the reviewer.

**Source-review no-go for the initial R2 integration at `8fbd4130`**, with GACT `3efef4af` and marketplace `3299065f`. The architecture is substantially simpler, but several production paths still violate the plan.

1. **[P1] Admission can remain blocked after Core recovers.**  
   The initial “busy” write occurs outside the recovery handling. If it fails, `requires_recovery` blocks subsequent admission, but this path schedules no recovery callback. Pending messages can remain stranded indefinitely. Route admission/start failures through the existing recovery mechanism.  
   [conversations.py:444](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:444)

2. **[P1] Module variants bypass input commitment.**  
   Variant attempts deliberately stage no mailbox input, while the enclosing module has no corresponding input commit. Returning an open draft Question therefore leaves the triggering message pending; TurnRunner can repeatedly admit it and immediately yield again. Commit the shared input once before branching, and explicitly handle subsequent Question continuations.  
   [clio_react_record.py:471](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:471), [variant_drafts.py:751](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/variant_drafts.py:751)

3. **[P1] Native monitoring stops permanently after a visibility error.**  
   `_drive()` records uncertainty and exits. If Core successfully records that observation, nothing schedules reconnection to the original `ToolTask`. The physical workload can finish without its task settling; shutdown subsequently waits for settlement indefinitely.  
   [native_tools.py:351](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:351)

4. **[P1] Subtree cancellation abandons eventual settlement after uncertainty.**  
   When any descendant becomes uncertain, `_cancel_subtree()` publishes attention, returns and removes its listener. Even if that descendant later recovers and confirms cleanup, no remaining callback finalizes the parent cancellation. Keep the existing owner’s reconciliation pending until the final outcome is known.  
   [conversations.py:749](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:749)

5. **[P1] Migration can resurrect withdrawn work and disabled subscriptions.**  
   The importer reads accepted mail without applying legacy withdrawal records, then recreates everything as eligible peer mail. It also reads `enabled`, whereas legacy subscriptions use `active`, and keeps the first imported subscription instead of folding subsequent changes. Preserve attribution, withdrawals and the latest relationship state.  
   [task_migration.py:193](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_migration.py:193)

6. **[P1 — missing implementation] Surviving provider-job reattachment is absent.**  
   Startup marks all previous memory-backed native work interrupted, including Downloads whose Globus job may still exist. The only caller of the retained provider polling algorithm is a newly executing native worker; there is no recovery path using the saved provider job ID. R2 explicitly requires this.  
   [native_tools.py:130](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:130)

7. **[P2] Restart waits on the wrong cancellation-job key.**  
   Cancel stores its job under `handle`; restart looks up `"cancel:" + handle`. Restart can consequently report unsettled cancellation immediately instead of awaiting the known cancellation job. Use one identity consistently.  
   [conversations.py:681](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:681)

8. **[P2] Queued subscription delivery ignores revoked observe permission.**  
   Publication checks both read and observe, but injection checks only read plus an enabled subscription. Revoke an independent observe grant after publication while retaining read: the queued notification still enters the recipient’s context. Recheck both rights at commitment.  
   [session_mail.py:140](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:140)

The simplification is real: the old registry, fold, mailbox and subscription machinery has been removed. Root and child assignments share an owner; workflow steps use ordinary child assignments; Questions use common task records; inference permits surround model calls; GACT now has grant/revoke and source-ownership wiring. **Keep those boundaries. These findings need corrections inside the existing owners, not another coordination layer.**

The earlier draft overwrite and explicit-refinement fixes are present, but finding 2 prevents accepting their integrated behavior. Independent-session/workflow rights and UI wiring likewise remain unqualified.

**No files changed, tests/checks run, or services/models launched.** Q1–Q9 and R1–R6 remain outstanding for this integration; earlier component passes do not qualify this commit.


