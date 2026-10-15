**The direction is substantially better, but I would not approve the implementation yet.** I reviewed the current [replacement plan, revision R2](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md), against core `a529569d` and GACT `458313c`. I couldn’t identify a separate current document labeled V2.

Three findings matter:

1. **[P1] Failed collection recovery can strand later conversation turns.** If a task result is recorded, its input commit fails, and its read grant is subsequently revoked, every following model-input commit retries that inaccessible observation and raises again. Unrelated human feedback cannot proceed. The recovery loop needs to retain a safe, denied observation while allowing ordinary input to continue. The existing regression checks the denial but stops before testing continued conversation. [Recovery loop](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:406), [existing test](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_arc/test_task_collection_authorization.py:298).

2. **[P2] Pagination still performs whole-history work.** Each task page enumerates all matching candidates, checks them, sorts the entire result, and only then applies the cursor. Loading more pages repeats that work under the shared history lock. With unlimited retained history and periodic Runs refreshes, this contradicts the plan’s bounded-read requirement. Pagination should advance through the existing indexes. [Query implementation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:93).

3. **[P2] Workflow UI obscures known failures.** When step A fails and later steps were never launched, their missing task handles make Runs display **“unknown”**, with a misleading explanation that statuses are not loaded. The backend already records the failed step. Use that recorded workflow outcome and distinguish “not launched” from “task visibility unavailable.” [UI inference](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/routes/runs-page.tsx:223).

On your concern about overengineering: **the simplification is real.** The old task registry, native host, journal, completion-wake policy and custom MCP driver are deleted. Native execution, conversation assignments and durable delivery now have clearer owners. That is a meaningful improvement over layering more recovery mechanisms onto the previous system.

My recommendation is to keep this ownership design and fix these issues inside the existing owners. The remaining risk is recovery bookkeeping and expensive projections spreading back into ordinary execution.

This was source review only; I changed nothing and ran no tests. The acceptance ledger still lists focused execution, CI and fresh live acceptance as pending.
