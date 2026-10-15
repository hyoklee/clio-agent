# Independent Claude Code Fable review R31

Core 3d929627; GACT 30df56ed. Committed source, acceptance ledger and correction maps; neutral two-paragraph brief; read-only source review.

## Verdicts

**Architecture/source: conditional NO-GO.** The core replacement is coherent and single-owner. One writer, one admission path, one Question owner, one notice path and one cancel dispatcher are all present and consistent. Two concrete defects block approval: the GACT Runs page targets routes core no longer serves, and Stop-held or cancel-held human inputs have an incomplete lifecycle with no regression coverage.

**Qualification: NO-GO.** Every ledger row from F01 through Z05 remains blocked or unexecuted. Nothing I inspected changes that. The Runs page defect would fail U01 and Q9 on first live contact.

Caveats on what I could inspect:
- The package has no git metadata, so I cannot confirm it matches core 3d929627 or GACT 30df56ed. The owner file names the core revision; I took GACT identity from the user statement.
- The marketplace submodule at 9257bba is absent from the package. D01's marketplace prompt review could not be performed. The core prompt pack and tool descriptions were reviewed.

## Findings

**1. GACT Runs page depends on routes that do not exist in core. Blocking.**
`external/gact-tui/web/src/routes/runs-page.tsx:268-277` loads rows through `repository.runs` and `repository.relayStatus`. Those call `GET /v1/runs` at `packages/core/src/v3/repository.ts:285-293` and `GET /v1/relay/status` at `repository.ts:352-359`. A search of `src/clio_agent` finds no route for either path, consistent with the plan's removal of `run_registry`, `routes/agent_tasks` and relay routes. The executions tab therefore renders the error branch at `runs-page.tsx:512` against the replacement service. `repository.ts:562-569` also posts to `/v1/agent-tasks/{id}/cancel`, which core does not register; it is unused by the web app, so it is dead code rather than a live break. The relay settings, infrastructure and managed-services components still call relay routes. The plan allows absent relay runtime but requires documented unavailable visibility, not request failures. This is the same class as the R26 "missing alias" finding.

**2. Held human inputs after Stop or cancel have no complete lifecycle and no tests. Medium.**
`conversations.py:680-703` holds the uncommitted trigger as `stopped_before_input_commit` or `cancelled_before_input_commit`. The only release is `conversations.py:266-283`, which re-promotes stopped items solely when another eligible item arrives, and never re-promotes cancelled ones. Retry supersession at `turn.py:655-666` and `session_input.py:30` recognises only `hook_blocked` and `execution_failed_before_input_commit`, so a Stop followed by a retry of the same message delivers both copies in the next segment. A cancelled-before-commit input stays pending indefinitely, visible only through the mailbox route. No test in `tests/` references either reason. M07 says undelivered input is withdrawn or deliverable, not retained in limbo. This needs a decision and regression cases, not necessarily new machinery.

**3. Fresh assignments display as yielded. Low.**
`conversation_assignments.py:166` creates assignments with activity `idle`. `routes/tasks.py:76` and the UI decoder at `packages/core/src/v3/schemas.ts:139` map idle to yielded. A child that has never run shows "The assignment is still open" text in `task-activity-row.tsx:118-122`. Queued would be honest.

**4. Subscriber authorization impersonates the owner's human. Low.**
`task_publication.py:53-58` and `task_runtime.py:354-356` build the subscriber's caller with the task owner's human id. `session_mail.py:296-301` derives the sender's human from its own assignment. Harmless under one principal, but the two derivations disagree and the first would leak under multiple humans.

**5. Reads publish owner notices. Low, ownership smell.**
`task_declarations.py:67-70` calls `publish_task_notice` for every finished handle on `wait_tasks` and `get_task_result`, including when the caller is only a grant holder. It is idempotent and never acknowledges, but a peer read becomes a writer of the owner's mail.

**6. Unnecessary complexity.**
- `task_declarations.py:290-300` re-derives the Question handle and re-checks the prior snapshot that `questions.py:60-86` already handles.
- `task_operations.py:331` duplicates the cursor recipient check in `task_observations.py:29-34`.
- `task_declarations.py:163-170` authorizes a peer message, then `session_mail.py:339-350` authorizes it again.
- `routes/tasks.py:220` reaches into `SessionMail._authorized`.
- `task_history.py:413` imports a token estimator from the ReAct recorder into the Core writer.
- The replay snapshot and rollback boilerplate in `task_history_projection.py:171-273` manages about thirty parallel dicts by hand. A single state object would shrink it and remove a class of partial-rollback bugs.

**7. Competing ownership: none found in the reviewed scope.**
Mail producers across `human_controls`, `session_input`, `turn`, `routes/mailbox`, `a2ui_actions/delivery`, `spotter_watcher`, `conversation_*`, `session_mail` and migration all persist and signal only. Admission is exclusively `TurnRunner` driven by `Conversations._admit`. Goal waits record dependencies through `conversations.set_dependencies` at `goal_control.py:17`. The only loops are CoreRecovery backoff and the post-result thread-exit check in `turn_runner.py:199-201`, which R26 accepted. Native and external owner loops were not reviewed in depth here.

## Conformance confirmed in the focus areas

- Addressing: tree rights are lineage based at `task_access.py:37-47`; children get no ancestor or sibling rights; the delegation-reply grant at `conversation_assignments.py:515-529` is message-only; historical exact grants do not retarget successors per `task_access.py:98-119`.
- Waiting: atomic snapshot, register and recheck with handle and recipient listeners at `task_operations.py:237-254`; revocation wakes waiters; the any-wait error contract is preserved; agents cannot wait on their own active assignment while humans can.
- Messaging: pending-only peer cap counts staged peers only; human input and results are exempt; busy arrivals enter the next iteration through the same pump.
- Questions: posting is immediate with no worker; Stop leaves the Question open; expiry is arbitrated under the writer lock and re-armed on restore by `question_events.py:125-150`; collection through shared waits uses the durable observation and re-authorizes every member at commit per R27 and R28.
- Workflows: checkpoints go through the confirmed writer; a historical invocation cannot advance a retry; step children carry accumulated state through the committed launch context.

## Regression coverage

Fresh suites under `tests/test_arc/` cover the writer, collection authorization, conversation owner, workflow checkpoints, Question resolution, hook approvals, route aliases and migration. Gaps I found: no cases for finding 2, no UI test exercising the Runs page against actual service routes, and no route test for the bearer-gated grant endpoints or the mailbox projection. Static checks have run; no test was executed in this review.
