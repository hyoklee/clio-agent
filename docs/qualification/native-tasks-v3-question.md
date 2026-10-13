# Question tasks in the native V3 integration

The requested extension uses the existing question owner and Core history. It
adds a `Question` projection to the shared controls; it adds no scheduler, worker
pool or competing mailbox. `ask_user` is a short FastMCP control that returns a
durable handle before an answer exists. `wait_tasks`, `observe_tasks`,
`cancel_tasks` and `get_task_result` use the existing shared operations.

Answers use the recipient-input commit used by other task results. A running
agent receives eligible answers at its next model iteration; an idle or stopped
agent can wake. Explicit collection and automatic delivery share the guard.
Stop ends the waiter, not the question. Closing the response dialog dismisses
only that dialog. Permission, plan and external MCP input gates remain distinct.

## Focused qualification

The 33 exact backend cases and their disposable-root receipts are recorded in
[`native-tasks-v3-question-checks.json`](native-tasks-v3-question-checks.json).
Additional generic transcript interruption checks cover cancelled, interrupted
and failed model segments without changing accepted task states. Both live-event
and reload projections close an unanswered tool invocation without fabricating a
result. Recorded results and other turns retain their original states.

Scoped Ruff, Pyright, frontend lint/types and size/instrumentation/fallback guards
pass. Online and offline UI builds pass. The three ordinary transcript golden
comparisons pass without changing their recorded content. Existing native
binding leak warnings and CSS/offline build warnings remain observations.

## Actual model evidence

These are production tool bridges, isolated source services and real Core,
not executor-only probes. Credentials were copied without refresh capability;
original authentication and the installed application were not changed.

| Case | Frozen core | Proof under `D:/Temp/` | Result |
| --- | --- | --- | --- |
| Luna explicit wait | `f4a83885` | `clio-v3-question-live-e9dcef0a/proof` | Passed: handle, independent file read while pending, expired wait, observation, unbounded wait and stored answer. |
| Luna idle answer | `f4a83885` | `clio-v3-question-idle-0660cf74/proof` | Passed: yielded execution, later answer, automatic wake and collection. |
| Luna Stop | `45faf34b` | `clio-v3-question-stopfinal-d411995a/proof` | Passed: cancelled segment settled, question remained pending, answer woke model and was collected. |
| Claude explicit wait | `45faf34b` | `clio-v3-question-claude-c13a91c2/proof` | Failed overlap gate: independent read preceded successful acceptance. The question subsequently answered/collected successfully. Retained as a failed qualification run. |

Two earlier Stop drivers failed to recognize the endpoint's successful 204 or
its cancelled segment state. A third old run eventually collected the answer but
had already timed out its pre-answer settlement gate; it is not accepted as the
strict Stop case. A prolonged UI hold on the first failed driver became
unresponsive after a late UI answer; its cause remains unestablished. Those runs
are retained as failures, and all their owned service/Core processes settled.

Each listed family removed its disposable credential copies, caches, workspace,
application state and private Core runtime after settlement. Only small logs,
receipts and images remain. Rejected old captures are not website acceptance.

## Remaining gates

Current integrated-source repetitions, the distinct Claude bridge and real
desktop/phone UI review are still pending. This extension's evidence does not
complete the broader V3 workload, recovery, session/workflow and CI matrix. Old
task-engine evidence is not acceptance of its replacement.

## Cleanup boundary

The prior single-file removal of `D:/Temp/clio-v3-pr1704-62b77512.md` was rejected
by automatic review as `blocked by policy`; it did not run. That exact small
temporary PR-body file is manual-only and is not retried or bypassed. This does
not change cleanup ownership for freshly created qualification state.
