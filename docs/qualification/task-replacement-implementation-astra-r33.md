# Independent Astra implementation review R33

Review turn `01a13ea6-d4f7-7693-8ec4-a44139d57b6d`; read-only source inspection. Reviewed source core `9c553b29` / GACT `3a753c4d`; the last two commits change UI test assertions only.

**The replacement direction is sound, but the current implementation still needs corrections.**

I reviewed [task-replacement-plan.md, revision R2](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md)—the second revision available on disk. I found no separate V2 document. Source reviewed: core `9c553b29`, GACT `3a753c4d`.

The plan addresses the overengineering in concrete ways:

- Removes the competing task registries, custom execution drivers and duplicate wake policies.
- Gives conversation admission to `TurnRunner`, execution to the relevant workload owner, and delivery acknowledgement to one recipient-input record.
- Preserves stable sessions while making assignments finite.
- Treats uncertain recovery honestly, without building a universal exactly-once execution system.

Those removals are visible in the replacement source. This is meaningful architectural simplification, even though the resulting code remains substantial.

**Two concrete implementation gaps remain:**

1. **[P2] Observe-only waits bypass the final authorization check.**
   `wait_tasks` can return an observe-only task’s status/progress, but [_collected](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:53) records only completed readable results. The observe-only outcome loses its authorization metadata. Revoking access between tool completion and model-input commitment therefore does not prevent that metadata entering context. Preserve each outcome’s required permission through the existing observation/commit path, including compatibility aliases.

2. **[P2] Runs can report an unfinished workflow as completed.**
   If step A completes and step B’s predicate is unsatisfied, the runner records the stalled state. However, [Runs excludes unstarted steps](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/routes/runs-page.tsx:223) and concludes that all remaining steps completed. The UI should respect the recorded workflow outcome and require completion of the declared workflow—not just its launched subset.

My main recommendation is to **freeze the architecture and feature scope now**. Fix these through existing owners, then finish the acceptance matrix. Another generic coordinator, recovery service or delivery state machine would undermine the simplification. The plan already contains enough machinery.

The [acceptance ledger](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/qualification/task-replacement-acceptance.md:313) still leaves source approval, migrated regressions, performance evidence, exact-head CI and live qualification outstanding. My verdict is therefore **approve the architectural direction; do not accept the implementation or release yet**. This was source inspection only; I changed nothing and ran no tests.

On your earlier question: compaction condenses conversation context so work can continue beyond the normal context window. It preserves key state using fewer tokens; details may need rechecking. [OpenAI documentation](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide#compaction).
