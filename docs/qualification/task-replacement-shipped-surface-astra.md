**The simplification direction is right, but the compatibility contract is incomplete.** I would fix that before calling the replacement ready.

The files now contain a **V3 design and R2 replacement plan**. I reviewed those against feature head `1fb99459` plus its current source edits, using released `v0.9.5-beta.5.2` as the compatibility baseline.

R2 makes the right architectural distinction: native execution owns workloads, the conversation engine owns assignments, and Core records history and delivery. It explicitly removes competing registries, drivers, and wake policies. That addresses the overbuilding. The remaining problem is that deleting those implementations has also removed useful shipped interfaces.

The concrete gaps are:

- **Fanout breaks existing calls.** Released `spawn_agents_parallel(spawns=...)` became `assignments=...`. Its entries also lost `blueprint_id` and `input_task_ids`, and bypass the blueprint resolver used by single spawn. [Current implementation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:485)
- **The observation alias preserves only its name.** Released arguments include `cursor`, `limit`, `pattern`, and `include_state`; the replacement accepts only `task_ids` and `timeout_s`. Existing incremental observation and pattern waits therefore break. [Compatibility implementation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:407)
- **`message_agent` is missing**, despite being released. Conversely, the compatibility document calls `cancel_agent_tasks` shipped, but that name is absent from the selected release. [Current compatibility table](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/runtime/task-compatibility.md:7)
- **Single spawn lost result handoff through `input_task_ids`.** That removes the useful “researchers → critic” workflow where the parent passes references instead of ingesting and resending all the evidence. [Single-spawn declaration](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:463)

I would settle the whole surface with this finite mapping:

| Released surface | Decision |
|---|---|
| `spawn_agent_task(agent, task, blueprint_id, strategy)` | Retain through the conversation owner and common blueprint resolver. `strategy` existed in the released callable, although its explicit tool schema omitted it. |
| Single-spawn `input_task_ids` | Retain as validated, immutable result references in the child’s committed input. |
| `spawn_agents_parallel(spawns, placement)` | Preserve `spawns`. Each entry retains `agent`, `task`, `blueprint_id`, `input_task_ids`, and the callable-supported `strategy`. Use the same preparation path as single spawn. |
| Spawn `placement` | Special relay execution is explicitly removed by R2. Accept omitted/local placement through the local path; reject relay placement clearly. Never silently run a requested remote job locally. |
| `wait_agent_tasks(task_ids)` | Delegate to shared wait with `return_when="all"` and an unbounded default. `timeout_s` is an additive extension, not part of this released signature. |
| `observe_agent_tasks(task_ids, cursor=1, limit=40, pattern=None, include_state=True)` | Preserve these arguments through shared authorized observation. Translate legacy cursors using retained provenance; report unavailable history explicitly rather than silently resetting. Observe must remain non-consuming. |
| `get_agent_task_output(task_id)` | Keep the one-cycle delegate to canonical result collection. Current bounds and references are appropriate; describe them honestly. |
| `message_agent(task_id, message)` | Keep a one-cycle delegate to authorized session messaging. Active children receive boundary input; completed children follow the new eligible-successor rules. Historical task handles remain historical. |
| `cancel_agent_tasks` | No compatibility obligation established by this release. If retained, classify it as an additive alias to `cancel_tasks`. |
| `run_workflow(request)` | Retain the declared-workflow contract through the existing runner; it does not justify another workflow engine. |

The handoff needs one explicit architectural rule: **passing evidence is not granting access to another task.** Validate that each reference names the parent’s own finished child and remains readable, then attach the exact result reference—with provenance and any partial-output marker—to the new child’s fixed input. Do not copy transcripts, create sibling grants, or restore the old resolver/registry. An invalid reference must prevent that child from being created.

Compatibility also includes response envelopes: preserve useful fields such as `task_id`, fanout `spawned`, and wait `results` through thin formatting adapters. Those adapters must retain the canonical collection receipts; they must not introduce another acknowledgement mechanism.

My recommendation is **one compatibility correction covering this entire table**, followed by focused contract checks. Restoring missing interfaces individually risks recreating the patch-by-patch process you wanted to escape.

This was a read-only source review, not runtime acceptance; I changed no files and ran no tests.

Compaction, from your earlier question, compresses the conversation’s working context so a long chat can continue while retaining key prior state. [OpenAI documentation](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide#compaction)
