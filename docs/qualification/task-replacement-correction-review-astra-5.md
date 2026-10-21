# Independent correction review — Astra

Reviewed core e863510b, GACT2924500f. Source review only; no test or live acceptance.

**The four original findings are resolved at `e863510b`. Two defects remain in the variant changes.** Reviewed against `a7f2c86f`, with GACT pinned to `2924500f`.

1. **[P2] A later module-variant run can strand an earlier open choice.**  
   [`variant_drafts.py:792`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/variant_drafts.py:792) returns `None` when the existing Question is pending. `UserJudgedVariant.forward()` treats that as permission to start another run, whose `_pause()` overwrites the single `variant_pending` pointer at [line 489](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/variant_drafts.py:489). After another eligible turn, answering the first Question no longer resumes its run. Preserve continuation by Question/run identity, and distinguish “pending continuation” from “no continuation.” Cover two outstanding choices answered in reverse order.

2. **[P2] Ordinary draft-tool instructions promise behavior the asynchronous path no longer provides.**  
   [`variant_drafts.py:645`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/variant_drafts.py:645) still promises comment-driven refinement through `n` drafts and automatic turn completion with the selection. The ordinary path now releases its claim, creates no continuation pointer, and no longer calls `resume_pending()` from `ClioReAct.forward()`. Consequently, `judge=user, strategy=refine, n=3` generates the first draft, but its answer cannot reach the retained refinement loop. Complete that asynchronous continuation or deliberately revise the offered contract and instructions.

The original corrections hold up:

- Withdrawn/already-acknowledged input is rejected under the writer lock; identical committed-input replay remains allowed.
- Canonical preparation events recover input commitments after passive-index deletion.
- Shutdown shields adoption; recording failures retain accepted identity and support recording-only retry.
- Option-only Questions reject metadata-only and attachment-only answers.

I found no additional blocker in the reviewed schema-dialect selection, argument-digest check, transport identity/auth delegation, pending-only mailbox limits, or direct parent-cancellation admission check. GACT’s change is limited to installer dependency pins.

The committed receipts report executed component passes, distinguish the earlier setup failure and subsequent retry, and retain the nanobind exit diagnostics. I independently confirmed the installed dependency tuple. **The variant receipts test posting/answering, not the continuation cases above.**

This was a read-only review of the frozen correction slice and its evidence. No tests, services or models were run. Later workload wiring, shared admission, migration, UI and live acceptance remain pending; these findings do not imply those stages are complete.


