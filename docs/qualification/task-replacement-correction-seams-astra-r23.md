**Yes—all five fit the R2 owners, with the conditions below.** No additional scheduler, lifecycle owner or store is needed.

1. **Cancellation retry:** re-arm only the exact failed request through `CoreRecovery`. Retry genuine recording failures; finish the entry once the cancellation is durably recorded or its existing owner has accepted responsibility for delivery. An unavailable external binding remains uncertain, without a repeating retry. Passive listeners only reassess settlement.

2. **Orphan recovery:** close unanswered calls before their next thought/user/summary boundary. Preserve original segment IDs and relative order; insert synthetic observations into the appropriate step rather than renumbering retained evidence. Mark uncertainty explicitly and never replay the operation.

3. **Empty workflow request:** approve. Require `request` to be a string, allowing `""`; keep nonempty validation for execution, invocation and declaration identities.

4. **Context epoch:** approve as conversation-owned assignment data. Use a deterministic epoch bound to the exact Question, persist it before clearing the gate, capture it at admission, and preserve it through [both turn setters](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_state.py:291). Same-session successors inherit it; separate child sessions retain their own context identity.

   Two companion changes are necessary:

   - [Recovery currently skips every epoch scope](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/context_identity.py:38). Permit recovery of evidence belonging to an already-used epoch. A fresh epoch must not import the preceding transcript; History-mode fallback needs an explicit post-clear boundary.
   - Recovery must not reuse an old epoch’s `ContextBoundary` or committed input as input to the new epoch. Preserve their historical receipts, but select recovery evidence matching the admitted epoch.

   Repeating the same Question repair must reuse the epoch and preserve work already recorded within it.

5. **Frozen plan resolution:** a **server-authored, immutable content reference in Question details** is the smallest common solution I found. The Question owner should confirm content first, then attach the reference under the existing writer lock. Bind it to the exact Question and accepted decision; preserve the original prompt, options, answer, status and terminal timestamp. The current [terminal-outcome guard](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:245) permits details enrichment without replacing the answer.

   Capture everything needed to repeat the effects: decision, clear boundary/epoch, approved plan content, captured artifact reference or explicit degraded outcome, and deterministic resume payload where applicable. Every retry reads that reference before changing mode, transitioning the playbook, clearing context or staging mail.

   **Avoid a preparation loophole:** calling `save_approved_plan()` against the mutable file before freezing the payload still permits drift after a failed reference write. Reuse the captured review snapshot; for legacy/degraded cases, freeze the available content and degradation explicitly. Any later artifact registration must consume that pinned content.

There is no simpler existing record covering all of (5): approval mail excludes `exit_only`, the terminal Question result already represents the immutable answer, and session metadata can be replaced by later decisions. The Question-details reference handles `exit_only` without creating wake-up mail.

This approves the proposed design boundaries only. No edits or tests were performed; strict R2 restart holds remain unchanged.
