+# Independent Astra source review

Core `90a7db56ac782167859426bed5993fb8f523b841`; GACT `f1b099cdf479a4e2516391a525efeba17799cd65`. Existing review chat `01a131d2-519c-7ec2-b9a5-5a7ab0efe495`, completed turn `01a138f8-27bc-7303-b990-a501370602a3`. Read-only source review; no runtime acceptance.

**The architecture is improving, but the frozen implementation remains a source-level no-go.** Reviewed core `90a7db56` with GACT `f1b099cd` against R2.

Six actionable findings:

1. **[P1] Application imports are still broken.**
   [client_state.py:39](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/a2ui_actions/client_state.py:39) and `dispatcher.py` import `deliver_to_agent`, but its module no longer defines it. This blocks application import and the reported test collection. Rebuild these callers against the new mailbox/input boundary.

2. **[P1] Native task submission fails on Linux.**
   [native_identity.py:24](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_identity.py:24) calls `psutil.Process.create_time(monotonic=True)`. The pinned public API accepts no such argument. With a normal Linux boot ID, identity capture raises before Shell/Download/Indexing submission. The test’s fake accepts the unsupported argument, hiding the defect.

3. **[P1] Native cancellation delivery still disappears across acceptance and restart.**
   [native_tools.py:977](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:977) returns uncertainty when acceptance is unavailable without registering cancellation delivery. Later adoption never sends it. Startup also restores observation without reissuing persisted cancellation intent. Consequently, already-started work can continue after cancellation. Retry delivery against the verified original identity when adoption or restoration succeeds.

4. **[P1] Paused assignments skip cancellation recovery.**
   [conversations.py:172](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:172) checks the persisted pause flag before pending cancellation. Pause → cancel → service restart can therefore leave the assignment without its cancellation/settlement worker, even after descendants finish. Recover cancellation before applying the model pause gate.

5. **[P2] Provider continuation can lose predecessor-cleanup evidence during a Core outage.**
   [native_storage.py:241](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_storage.py:241) writes predecessor receipts without retaining a retry. The enclosing recovery path preserves only the current attempt’s receipt. If the predecessor write fails before commit, cleanup can succeed physically while the public task remains uncertain indefinitely. Retain and retry that specific evidence write.

6. **[P2] Waiting through retained aliases can miss completion.**
   [task_operations.py:134](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:134) subscribes using the supplied alias, while history emits changes under the canonical handle. An authorized peer without a result subscription can remain asleep after completion; pattern observation has the same issue. Resolve aliases before registering listeners.

The consolidation itself is meaningful: shared Core records/mailbox, workload-specific execution owners, and one conversation admission path. The earlier Download ordering, cancellation membership capture, held-result collection, variant feedback, and spawn-strategy corrections are present.

These findings call for bounded fixes within those owners. They do **not** justify another scheduler or reconciliation framework.

This was read-only source review. I made no edits or test launches; CI and live acceptance remain separate, outstanding gates.
