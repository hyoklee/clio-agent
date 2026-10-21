# Independent Claude Code review R18

Actual model: claude-sonnet-5-5; CLI2.1.296; remote existing host login. Read/Grep/Glob only, no MCP servers, no session persistence. Frozen core source19319a3b, test/docs head9486991a; GACTce99316446848ddd269b1bf782ff2c87cc9db14a; marketplace9257bba5953b012ba796299df4c633e698dbaddc. Source snapshot SHA256cdbfcf2ba7ad9e1c73d551ca80b1a8537f2379be56584c5d6e97b9b817b81057. No tests, builds, services or live product models were run.

# R18 independent review: CLIO Tasks R2 production source

**Verdict: not ready for initial production.** I found one P1 and three P2 defects, listed below. The P1 permanently wedges a session after a routine cancel. I read the plan, the wiring, access and operations, history and mailbox, conversations, native work and settlement, the SDK boundary, the Question and workflow code, and the REST and human-control routes. I did not read every file, and I ran no tests or commands.

## P1

**1. Cancelling an assignment that owns an external MCP task wedges the session permanently.**
- Trigger: cancel (human, `cancel_tasks`, or Stop-then-cancel) an assignment whose subtree has an active external MCP or inline task. A second route has the same effect: an external task that terminates naturally after the cancel snapshot. That route is a narrower window, and I did not trace it as far.
- Chain, in order:
  - `external_tasks.py:740-777` sets the cancellation intent and calls the SDK cancel.
  - The server then reports `cancelled` or `completed`. `external_task_inputs.py:80-92` turns that into `status=task_state_uncertain`, `terminal_at=None`, `settlement="unknown"`, `result=None`. The inline path does the same at `external_tasks.py:683-695`.
  - Later replies hit the same branch, so the task never reaches a terminal state.
  - Without a cancel request, an external terminal gets `settlement="external_acknowledged"` (`external_task_inputs.py:75`, `external_tasks.py:678`).
  - `_cancel_subtree` accepts only `confirmed` or `never_started` as settled (`conversation_controls.py:487-496`). Anything else is treated as uncertain (`:497-505`), so the loop never breaks and the parent is never finalized as `cancelled`.
- Consequence:
  - `Conversations.eligible` returns False for every item, including human messages, while the assignment has a cancellation request and is not terminal (`conversations.py:204-206`).
  - `require_admission` closes spawn, `ask_user` and native submission (`conversations.py:460-463`).
  - Restart requires a settled assignment, so it refuses (`conversation_controls.py:304-313`).
  - I found no human or force-close path to resolve it (grep for force-close, abandon and similar terms found nothing relevant).
  - The only option is to abandon the session.
- The plan says external acknowledgement is not proof of cleanup. That justifies an attention episode, but not a permanent block on the parent. Cancellation of the parent needs a bounded outcome: for example, an explicit human acceptance of uncertainty, or recording the external member as unknown-but-not-blocking.

## P2

**2. Pause followed by cancel leaves the session paused, with no direct way out.**
- Trigger: pause an assignment, then cancel it (or cancel via an ancestor).
- Cause: `pause` sets `_paused` and `metadata.agent_paused` (`conversation_controls.py:71, 125`). Neither `cancel` nor `_cancel_subtree` clears them. `resume` is the only code that clears them (`:148, 186`), and it rejects a terminal assignment (`:143`).
- Consequence:
  - Every later input, including human messages, is vetoed by `eligible` (`conversations.py:166`).
  - The terminal assignment's supported actions are only `get_result`, `message` and `restart`.
  - A workaround exists: `restart` creates a successor, then `resume` on the successor. It is not discoverable, and the human's pending message sits unprocessed until then.

**3. A declared workflow step budget (`timeout_s`) bounds nothing.**
- Location: `workflows.py:566-577`.
- Behaviour: expiry only ends the waiter and returns `workflow_step_timeout`. The child keeps running, and the next `run_workflow` call restarts the timer.
- Consequence: a pack-declared hard wall (`workflows.py:74-79`) is not enforced.
- Related: a failed step leaves no retry path. The step row already exists, so a re-call returns `STALL_CHILD_FAILED` again, and changed inputs are rejected as an "unfinished workflow". Only a restart or a new assignment recovers.

**4. With a persistent native backend, work that survives a restart can never settle.**
- Trigger: persistent (non-`memory://`) native backend plus a process restart.
- Cause: `native_task_recovery.py:117-124` marks every pending attempt's cleanup as `unknown`. `_settle` then stays `task_state_uncertain` (`native_task_settlement.py:83-85`) even if Docket redelivers and the new leg finishes cleanly.
- Consequence: the task is never terminal, and it blocks subtree cancel in the same way as finding 1. This affects only the optional persistent configuration. The default `memory://` marks lost work as interrupted and is fine.

## P3 and verification notes

- `resume` on an active assignment that is not paused overwrites `busy` with `yielded` and injects an extra control mail (`conversation_controls.py:150-183`).
- `wait(return_when="any")` returns immediately when one handle is unavailable, because that counts as an outcome (`task_operations.py:200`).
- `_collected` acknowledges a result after the first page of a paginated result (`task_declarations.py:53-75`).
- Every built-in short tool call does several Core writes and reads under the global history lock (`builtin_boundary.py:168`, `task_history.py:300-313`). This is a performance risk to measure, not a defect I confirmed.

## Checked and found sound

- **Authorization:**
  - Rights are evaluated before disclosure, filtering and pagination.
  - The injection-time recheck covers peers, subscribers and revoked grants (`session_mail.py:245-276`).
  - Grants are human-authenticated and have no assignment-scoped form.
- **Cursors and output:** cursor continuations validate task-local provenance (`task_output_pages.py:38-51`), so I found no cross-session read.
- **Delivery:**
  - The recipient-input record is the only acknowledgement.
  - Commits recheck eligibility and authorization.
  - Replay re-derives interrupted commits.
- **Native work:**
  - Native admission is shielded across cancellation.
  - Incarnations are unique.
  - Cleanup receipts are bound to their own incarnation.
  - Foreground Stop waits for physical cleanup.
- **Stop and admission:**
  - The `TurnRunner` pump keeps session ownership until the worker actually exits.
  - Admission is closed on shutdown.
- **Questions:** Question post, answer and cancel arbitration is serialized under the writer lock, and expiry is arbitrated against answers.
- **Source attachment:** `prepare_connect(human_action=True)` follows the permission gate already run in `native_call`, so there is no bypass.

## Acceptance gaps (not counted as defects)

Test migration, exact-head CI and the Q1–Q9 live matrix with the R1–R6 repeats remain outstanding. Findings 1, 2 and 4 are exactly what Q4, Q6, Q7 and R6 should exercise. The 4,648-file snapshot is only partly covered.

## Not reviewed

- Web UI components.
- `task_migration*` (the idempotence and unknown-delivery requirements).
- `external_tasks.py` lines 1–560 (acceptance and reconnect), and the rest of `native_storage.py`.
- `shell_server` and the Globus and provider algorithms.
- The Codex and Claude bridge async conversions.
- `clio_react.py`, `turn.py` and the goal, loop and schedule producers.
- `task_result_content` and `assignment_evidence`.
- Config defaults, prompt packs and the arc schema.