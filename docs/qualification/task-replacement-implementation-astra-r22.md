**Source NO-GO for `b9765992`.** The main R20 corrections are present, but five gaps remain.

1. **[P1] Failed descendant cancellation can lose its retry.**
   [conversation_controls.py:545](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:545) removes the failed-request retry along with repeated passive cancellation. If cancelling a pending Question fails before its close is persisted, the Question owner registers no retry. Core recovery restores the still-pending Question; the parent keeps waiting and orderly shutdown can block. Retain recovery for the **specific failed cancellation request**, independently of passive settlement rechecks.

2. **[P2] Orphan tool recovery still fails when another message follows the unanswered call.**
   [context_identity.py:83](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/context_identity.py:83) appends synthetic uncertain results at the end of the entire recovered context. However, `fold_steps` closes a tool step at the next thought, user message or summary and immediately rejects unanswered calls. Insert the uncertain result before that step’s closing boundary. The current correction handles a trailing orphan, but not an earlier one.

3. **[P2] Legacy workflow replay excludes the valid default empty request.**
   [task_history_projection.py:285](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history_projection.py:285) requires `request` to be nonempty when rebuilding historical invocation bindings. `run_workflow` defaults to `request=""`. Consequently, older invocation A can remain unindexed after retry B exists, and A’s replay falls through to B’s unfinished execution—the original R20 identity bug. Accept an empty string while retaining nonempty checks for identity fields.

4. **[P2] Plan “clear context” still leaves the model’s context intact.**
   [plan_exit_resolution.py:178](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/plan_exit_resolution.py:178) filters the transcript and sets metadata. Its [replacement helper](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_store.py:287) explicitly leaves ARC working-set scopes untouched. `ContextReader` continues reading those scopes, and no consumer applies the clear marker. Thus execution can retain the supposedly cleared planning context. Apply an idempotent model-context boundary while preserving Core history and newer pending inputs.

5. **[P2] Legacy/degraded plan approval retries can change the deterministic resume payload.**
   Without a successfully captured artifact, [plan_exit_resolution.py:160](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/plan_exit_resolution.py:160) rereads and remints from the mutable plan file on every repair. If resume mail was committed but gate clearing failed, a changed or missing file produces different content for the same `plan-answer:<question>` identity. `accept_session_input` then rejects every retry, leaving the gate stuck. Reuse the already-confirmed decision payload; content-hash deduplication alone does not make this retry idempotent.

The following corrections now look sound at source level: assignment-bound pause restoration; deferred-completion deadline enforcement; normal historical workflow lookup and launch-state delivery; post-compaction suffix preservation and thinking/text grouping; unknown-attempt attention; captured-schema settlement after SDK retirement; selected-identity refresh; and removal of cancellation RPCs from passive observation callbacks.

I inspected the additional ARC/History, trace-reader, plan/Question, visual-answer and native/external caller paths identified by R20. No additional required source group is deferred from that list. Strict R2 restart holds remain intentional.

No edits, tests, services or models were run. Static-check results remain reported evidence; behavioral tests, CI and Q/R acceptance remain unqualified.
