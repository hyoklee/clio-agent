# Independent Astra source review R27

**I would not approve R27 yet.** I reviewed committed core `5eab9ef8` and GACT `30df56ed` against R2. Two blocking defects remain in the shared input boundary.

1. **[P1] Recovery can expose a result after its read permission was revoked.**  
   Immediate collection now checks every `task_read_handles` entry, but [next-iteration commitment](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:410) reconstructs only notification IDs.

   A concrete case is a mixed wait containing an owned task and an authorized peer task **without a subscription**. The observation contains both results, but only the owned task has a recipient notification. If execution is interrupted after recording the observation, then the peer grant is revoked, recovery can acknowledge the owned notification and expose the entire retained observation—including the revoked peer result. The [writer’s coverage check](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history_projection.py:512) also checks notifications only.

   Recheck every persisted read handle inside the common input-commit boundary. The regression needs to exercise interrupted collection followed by `commit_input()` recovery; the new tests cover immediate collection with subscribed peers.

2. **[P2] Recovering a result during a human-triggered turn rejects valid human input.**  
   [The recorder](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:426) adds the human/composer notification to `staged.collected`. When a retained observation is also being committed, [SessionMail.commit](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:203) passes that entire collection to a validator accepting only `task_result` and `question_answer`.

   This occurs when human input queues before a result arrives, followed by interruption between observation persistence and commitment. Recovery selects the human message first and fails before calling the model.

   Validate result collection using the observation’s own notification IDs, while retaining ordinary human-input staging and acknowledgement.

The architecture remains defensible: execution owners retain their responsibilities, Core records history and delivery, and Questions use the shared input path. **These findings call for consolidating validation at the existing boundary**, which should remove duplicated policy.

R27 does address the earlier cancellation-RPC timeout, REST pagination, nonlocal-owner rejection, and stale cancellation-attention findings in source. Preserving the existing `any`-wait behavior is also correct.

This was a read-only source review, without tests or runtime reproduction. Implementation approval remains separate from the outstanding test migration, CI, and live qualification gates.


