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
| Luna explicit wait, UI and repetitions | `737dfc4f`, GACT `0501a04d` | `clio-v3-question-live-737dfc4f-c1/proof` | Passed baseline, real desktop/phone answer UI, five idle and five Stop cycles; each answer woke once and a later human follow-up did not redeliver it. |
| Claude explicit wait | `737dfc4f`, GACT `0501a04d` | `clio-v3-question-live-737dfc4f-c2/proof` | Baseline passed. UI setup and repetitions failed when installed-blueprint selection drained another session's question wait. Zero repetition cycles accepted. |
| Claude explicit wait and UI cancellation | `db6e2b1a`, GACT `e436740a` | `clio-v3-question-live-737dfc4f-c3/proof` | Baseline and real desktop/phone answer UI passed. Keep running preserved the question; confirmed cancellation settled it and reached the model. Two attributed human-intervention notices committed in the parent input. Seven repetition cycles passed, then the unchanged eight-iteration budget was exhausted before the required Stop wait. The family repetition gate failed. |

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

The corrected root Question runtime passed twenty repetitions on frozen core
`c5bcf10f18684644f7d43ecc9e589cc1bc9f3742` and GACT
`5809961b6de3e46b29518adecc9520bd66eed699`: five idle and five Stop cycles each
through actual Codex `gpt-6-luna` and Claude `haiku`. Both separate Stop baselines
also passed. Answers woke exactly once; a later ordinary human request did not
redeliver them. Wakes retained the original assignment; subsequent human
assignments had their own descriptions. Both families kept identical runtime
hashes throughout and removed all seven disposable children and their private
Core runtimes after settlement. Full identities, handles, receipts and failed
setup custody are in [`native-tasks-v3-question-live.json`](native-tasks-v3-question-live.json).

One launch used the invalid display alias `luna`, failing before any tool call.
It accepted no tasks and is retained as a setup failure, not a passing model run.
The Stop mission separates Stop from the already demonstrated expired-wait and
observe path within the unchanged eight-iteration budget. No validation, worker,
timeout or assertion budget was relaxed.

These are root Question acceptance results. They do not complete the broader V3
workload, child-route, recovery, session/workflow and CI matrix. Current broad CI
still has failures outside these accepted cases. Old task-engine evidence is
not acceptance of its replacement.

## Cleanup boundary

The prior single-file removal of `D:/Temp/clio-v3-pr1704-62b77512.md` was rejected
by automatic review as `blocked by policy`; it did not run. That exact small
temporary PR-body file is manual-only and is not retried or bypassed. This does
not change cleanup ownership for freshly created qualification state.

Automatic review separately rejected removal of this turn's generated site
`node_modules`, `dist`, `.astro` and `public/widgets` with `blocked by policy`.
The command did not execute. These exact residuals are manual-only; no helper,
parent deletion, move or alternative shell retries them. The ownership and
rejection receipts are `D:/Temp/v3-site-build-sideeffects-752.json` and
`D:/Temp/v3-site-cleanup-rejection-753.json`.
