# Astra adjudication of pre-input re-admission

**Fable’s main finding is valid and blocking, but “any failure before input commitment” overstates it.** This adjudication uses committed core `5eab9ef8`; I did not review the uncommitted correction packet.

Two paths can repeatedly admit the same input:

- **Hook denial repeatedly runs the same assignment.** [UserPromptSubmit](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/user_prompt.py:91) publishes a blocked/error result but neither holds nor acknowledges the trigger. [turn.py](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn.py:426) returns without a `ConversationOutcome`; [the adapter](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_runtime.py:285) converts that into an ordinary yield. The original input remains eligible, so admission selects it again. This branch produces repeated hook executions and history writes—not necessarily new failed assignments.
- **An admitted setup/agent-resolution error can produce successive failed assignments.** For example, an explicitly activated blueprint that cannot resolve raises `_NoResolvableAgent` before input commitment. The turn returns an error outcome, [finalization marks the assignment failed](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:251), and [admission creates its successor](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:290) from the same pending trigger. This repeats while the failure and admission conditions persist. Subagent failures can notify their parent; human-root completion does not notify itself.

[TurnRunner’s pump](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_runner.py:97) checks admission again after each segment. **Removing `_run`’s final signal alone would not stop this loop.** The session’s displayed `error` status also does not change mail eligibility.

Several cases are already gated:

| Case | Existing behavior |
|---|---|
| Agent construction unavailable | [The readiness gate](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_runtime.py:292) rejects admission while `app.state.agent is None`. `mark_agent_ready()` signals retained inputs after construction succeeds. |
| Deferred hook approval | `execution_gate` prevents admission while approval is pending. |
| Pause, Core recovery, shutdown | Existing admission/eligibility gates prevent repeated execution. |
| Stop before commitment | The trigger receives a durable hold. Its existing release rule is specific to Stop. |
| Exception inside admission itself | The pump exits its admission-error handler; it does not continuously retry without another signal. |
| Failure after input commitment | That trigger is already acknowledged, so this particular replay mechanism does not apply. |

**Retry and policy release need attention in the correction.** [Ordinary retry](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/sessions.py:804) creates a new input; it does not resolve the old uncommitted trigger. More concretely, [hook-defer resolution](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/hooks/defer.py:413) clears the gate and signals admission without holding or retiring the original prompt. Approval adds a later message carrying the skip-hook marker, but the earlier original can be selected first and defer again. Denial likewise leaves the rejected original eligible. Thus defer is gated **while pending**, but its release path has a related defect.

The smallest correction belongs in **conversation-owner finalization**, between `run_segment()` returning and the next admission:

1. Preserve an explicit veto/defer/error outcome instead of converting every early return into a normal yield.
2. If the attempted trigger has no recipient-input commitment, retain it with a reason using the existing mail hold mechanism. Do not fabricate an acknowledgement.
3. Make explicit retry or policy resolution release or supersede that exact input. Keep this distinct from Stop’s automatic release rule.

This requires no new scheduler or recovery engine. Focused regression coverage should establish one attempted execution per denial/error, no re-execution from unrelated signals, and correct explicit retry plus approval/denial release.

Source inspection only; no edits, tests, or services were run.
