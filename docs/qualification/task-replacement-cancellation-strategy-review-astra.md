# Focused Astra source/history decisions

Existing review chat: `01a131d2-519c-7ec2-b9a5-5a7ab0efe495`; completed turn `01a138d7-fb91-7931-ac09-bc16ea12a067`. Read-only; no tests or runtime acceptance.

**1. Keep the strict cancellation boundary. Do not add `external_acknowledged` to the accepted settlement states.**

Excluding tasks that were already terminal before this cancellation is correct. Their historical outcomes should remain unchanged. For work active when cancellation began, an external acknowledgement alone cannot justify confirmed subtree settlement or restart. The existing external owner may report stronger evidence; otherwise cancellation remains uncertain.

There is one necessary correction to the current construction: [conversations.py:758](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:758) waits for worker retirement **before** selecting nonterminal descendants. An external task can become terminal with `external_acknowledged` during that wait and disappear from the settlement obligations. Recovery repeats this problem by selecting against current state.

**Freeze cancellation membership when admission closes, before awaiting retirement, and preserve or reconstruct that membership through existing Core history.** Exclude genuinely earlier historical outcomes; retain tasks that became terminal during cancellation. This belongs in `Conversations`, without another owner.

Also, [external_tasks.py:378](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/external_tasks.py:378) uses `external_acknowledged` for generic terminal replies. Neither that label nor `terminal_at` establishes physical cleanup.

**2. Keep and rebuild spawn-time strategy. Remove the broken legacy adapter.**

Git history establishes that this predates the replacement branch:

- Introduced by `ac4a7b09`, explicitly supporting `spawn_agent_task(strategy=...)` and strategy per parallel-spawn entry.
- Included in release tags `v0.9.5-beta.1` (`b752b831`) through `v0.9.5-beta.5.2` (`711237db`).
- Still wired at `5475042f`: validation precedes child creation, normalized strategy enters child metadata, and the builder applies the module variant.
- Released tests cover LM/user judging, count caps, invalid-strategy refusal and child construction.

One qualification: the released single-spawn **curated argument schema omitted `strategy`**, despite its callable and description supporting it. Parallel entries were unrestricted objects and explicitly forwarded strategy. This was an incomplete public declaration, not evidence that the entire feature was unfinished branch machinery.

The smallest integration is:

1. Add optional strategy to the replacement single-spawn and parallel-entry schemas in [task_declarations.py:181](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:181).
2. Reuse [strategy_module()](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/module_variants.py:526) before creating a child. Translate its validation failure into the existing structured `invalid_strategy` refusal.
3. Pass normalized strategy through `Conversations.spawn` into child creation and accepted launch metadata; reject changed strategy for an already accepted invocation.
4. Retain the existing `with_session_strategy → wrap_module_variant` builder path. Human judging uses the existing Question/mailbox path.

**Keep strategy separate from trusted blueprint `target_scope`.** [task_runtime.py:102](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_runtime.py:102) checks that scope against installed configuration exactly; adding strategy to it would break that validation.

Delete or replace the dead `spawn_scope_with_strategy` wrapper and its undefined `SpawnError`; do not restore `turn_spawn`. Blueprint/module variants remain independently supported through the same variant implementation.

Read-only source/history decisions only. No edits, checks, services, qualification, or private review material accessed.
